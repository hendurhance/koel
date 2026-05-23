# Operations

How to run Koel in dev, deploy it, and keep it healthy.

---

## Local development

### With Docker

```bash
cp .env.example .env
docker compose up -d
docker compose exec api uv run alembic upgrade head
docker compose exec api uv run koel db seed
docker compose logs -f api worker
```

This brings up Postgres, Redis, the API, a Celery worker, and Celery beat. The two `exec` steps apply schema migrations and seed currencies + sources.

### Without Docker

Requires Python 3.12+, Postgres 14+, Redis 7+. On macOS:

```bash
brew install postgresql@14 redis
brew services start postgresql@14
brew services start redis
createdb koel
./scripts/setup-local.sh
uv run alembic upgrade head
uv run koel db seed
make dev   # starts api + worker + beat via honcho
```

`make dev` uses a `Procfile` under `honcho`. Individual processes:

```bash
uv run uvicorn koel.api.main:app --reload
uv run celery -A koel.tasks.celery_app worker --loglevel=info --queues=scraping,notifications,maintenance,usage
uv run celery -A koel.tasks.celery_app beat --loglevel=info
```

---

## Configuration

Everything is env-driven. `.env.example` has the full list with defaults. The values you'll most often want to tune:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres DSN in SQLAlchemy form |
| `REDIS_URL` | Redis URL shared by cache, sessions, broker, usage stream |
| `APP_SECRET` | Signs session cookies — **must** be rotated from default in prod |
| `APP_ENV` | `development` or `production`; flips log format from console to JSON |
| `INITIAL_ADMIN_EMAIL` | First user logging in with this email becomes admin |
| `SMTP_*` | Magic-link delivery |
| `SLACK_WEBHOOK_URL` | Empty disables Slack; set to activate |
| `SLACK_NOTIFY_ON_CRAWL` | Default `False` (crawl summaries are chatty) |
| `SLACK_NOTIFY_ON_CIRCUIT` | Default `True` |
| `BACKUP_ENABLED` + `BACKUP_S3_*` + `AWS_*` | Daily S3 backups |

---

## Migrations

```bash
uv run alembic upgrade head           # apply all
uv run alembic revision --autogenerate -m "add column"   # new migration
uv run alembic downgrade -1           # roll back one
```

Autogenerate reads the SQLAlchemy models; review the diff carefully — Alembic won't catch every case (partition definitions, check constraints, etc.).

---

## Backups

Daily at 04:00 UTC (beat schedule: `backup-daily`). You need:

```bash
BACKUP_ENABLED=True
BACKUP_S3_BUCKET=my-koel-backups
BACKUP_S3_PREFIX=prod/koel
BACKUP_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=…
AWS_SECRET_ACCESS_KEY=…
```

To run a backup on demand:

```bash
uv run celery -A koel.tasks.celery_app call koel.tasks.backup.daily_backup
```

Dumps are custom-format (`pg_dump -Fc`). Restore:

```bash
aws s3 cp s3://my-koel-backups/prod/koel/koel-20260421-040000.dump ./restore.dump
pg_restore --clean --if-exists -d postgresql://user:pass@host/koel ./restore.dump
```

---

## Observability

### Logs

`structlog` JSON in production, colored console in dev. Every request emits at least one `http.request.done` line with the `request_id` tag bound to every downstream log inside the handler. Grep by request ID to reconstruct a request:

```bash
docker compose logs api | grep 'request_id=abc123'
```

### Metrics

```bash
curl http://localhost:8000/metrics
```

Scrape with Prometheus. The sharp edges to watch:

- `koel_http_request_duration_seconds{route="…"}` — P99 latency per route.
- `koel_scrape_pairs_total{outcome="no_consensus"}` — rising count here means sources are disagreeing, which usually means one is returning stale / wrong data.
- `koel_circuit_transitions_total{from_status="closed",to_status="open"}` — a source just broke.
- `koel_backup_runs_total{outcome="failed"}` — a backup run failed; check the Slack alert.

### Slack

Set `SLACK_WEBHOOK_URL` to a Slack Incoming Webhook URL. You'll get notifications for:

- **Circuit opens / recovers** (source broke or came back).
- **Backup success / failure.**
- **Crawl cycle summaries** (off by default — set `SLACK_NOTIFY_ON_CRAWL=True` to opt in).

---

## Deployment

Koel is a stock Docker app; any host that runs Docker runs Koel. The Dockerfile is multi-stage and lands on `python:3.12-slim`.

### Deploy from published images

The `release` workflow (`.github/workflows/release.yml`) builds and pushes two multi-arch images (`linux/amd64` + `linux/arm64`) to GHCR on every `v*` tag:

- `ghcr.io/hendurhance/koel` — API, worker, and beat (same image, different commands).
- `ghcr.io/hendurhance/koel-frontend` — the Nuxt dashboard (standalone Nitro server).

Cut a release by pushing a tag; CI publishes `1.2.3`, `1.2`, and `latest`:

```bash
git tag v1.2.3 && git push origin v1.2.3
```

The first time, make both GHCR packages public (repo → Packages → each package → Package settings → Change visibility) so hosts can pull without authenticating.

On the host, deploy with the pull-and-run compose file — no source checkout, no build:

```bash
cp .env.example .env            # set APP_SECRET + SMTP_*; hosts are already postgres/redis
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api koel db seed
```

Pin a specific release with `KOEL_TAG` (e.g. `KOEL_TAG=1.2.3`); it defaults to the version baked into the compose file. Postgres and Redis are kept off the host network there — only the API (`:8000`) and dashboard (`:3000`) are published.

### Fly.io / Railway / Render

Point the service at the container, set the env vars above, attach a Postgres + Redis. Run one instance of each service type — `api` (any number), `worker` (any number), `beat` (**exactly one**).

### Exactly-one-beat

Celery Beat is not replica-safe. Running two Beat instances will double-schedule every periodic task. Enforce one of these:

- Only one `beat` container (recommended).
- Deploy a Redis-based leader election sidecar.

---

## Common operations

### Promote a user to admin

```bash
uv run koel admin promote you@example.com
```

### Drop an old partition manually

```bash
uv run celery -A koel.tasks.celery_app call koel.tasks.maintenance.drop_old_partitions
```

Partition maintenance runs daily; the manual call exists for incident response.

### Rotate the app secret

Flip `APP_SECRET` in `.env`, redeploy. All existing sessions will be invalidated — users will have to log in again. This is the intended behavior.

---

## Load + chaos testing

Before shipping a new major version (or any change that touches the hot path), run both gates.

### Load test

```bash
export KOEL_API_KEY=koel_xxxxxxxx
make load                      # 500 users, 50/s spawn, 5 min — see tests/load/README.md
```

CSV output lands in `build/loadtest_*.csv`. Pass criteria:
- `99%` on `/rates/current` ≤ 20 ms.
- Failure rate ≤ 0.1%.
- No sustained error bursts in `build/loadtest_failures.csv`.

For the 72-hour soak, override `RUN_TIME`:

```bash
RUN_TIME=72h make load
```

### Chaos runbook

See [`docs/chaos.md`](chaos.md) for the full rehearsal protocol (Postgres / Redis / worker / beat / source / S3 / SMTP / Slack / disk-full / 72h soak). Each scenario documents expected behavior, observables, and recovery. Run scenarios 1–8 on a staging stack before production deploy; scenarios 9 and 10 are pre-launch gates.
