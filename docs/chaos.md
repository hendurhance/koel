# Chaos runbook

Document what happens when each piece of Koel fails, how the system should behave, and how to recover. Use this as both an operator's reference and a pre-deploy rehearsal script.

Every scenario follows the same shape:

- **Kill** — the command that produces the failure.
- **Expected behavior** — what *should* happen automatically.
- **Observables** — logs, metrics, Slack messages you should see.
- **Recovery** — how to bring the system back.
- **Verified** — `☐` until an operator has actually rehearsed it; flip to `☑` after successful rehearsal.

All commands assume `docker compose`; translate to your orchestrator (Fly machines, Kubernetes pods, etc.) as appropriate.

---

## 1. Postgres down

- **Kill** — `docker compose stop postgres`
- **Expected** — `/healthz` still returns 200 (liveness only). `/readyz` returns 503 with `checks.database = "error: <ExceptionName>"`. Rate endpoints return 500. Celery workers log connection errors; `scrape_pair` tasks retry with backoff.
- **Observables** —
  - Metric: `koel_http_requests_total{route="/rates/current",status="500"}` rises.
  - Logs: `sqlalchemy.exc.OperationalError` in worker + api output.
  - Slack: no message (no circuit alert fires for a database outage — this is an infra-level event, not a scrape event).
- **Recovery** — `docker compose start postgres`. The connection pool recovers on the next request; no restart required for api/worker.
- **Verified** — ☐

## 2. Redis down

- **Kill** — `docker compose stop redis`
- **Expected** — Sessions fail (any authenticated endpoint 401s after token validation). Usage middleware logs a single warning per failed recording but does *not* fail the request. Celery beat and workers lose their broker — tasks stop firing. The circuit-breaker state store disappears; on recovery, circuits start from `closed` (one free retry per source — acceptable).
- **Observables** —
  - Logs: `redis.exceptions.ConnectionError`.
  - Metric: `koel_usage_events_flushed_total` stays flat.
  - Slack: no message.
- **Recovery** — `docker compose start redis`. Beat resumes on reconnect. Session store is empty — users must re-authenticate.
- **Verified** — ☐

## 3. Celery worker down

- **Kill** — `docker compose stop worker`
- **Expected** — API continues serving from the existing data. Beat keeps enqueuing scrape tasks; they pile up in the broker. Rates grow stale past their tier interval. Usage flush runs stop; events accumulate on the Redis stream (capped at `USAGE_STREAM_MAXLEN = 1_000_000`).
- **Observables** —
  - Metric: `koel_scrape_pairs_total` stops incrementing.
  - Metric: Redis `XLEN usage:stream:events` grows.
- **Recovery** — `docker compose start worker`. Queued scrape tasks drain in FIFO order; the usage flush catches up in batches of `USAGE_FLUSH_BATCH_SIZE`. If the backlog exceeds a few minutes of traffic, temporarily crank the flush beat cadence down.
- **Verified** — ☐

## 4. Celery beat down

- **Kill** — `docker compose stop beat`
- **Expected** — Workers keep processing any tasks still in the queue, then go idle. No new scrapes, no partition maintenance, no usage flushes, no daily backup, no cross-rate materialization. Rates go stale; history gaps form.
- **Observables** —
  - Metric: `koel_scrape_pairs_total` stops.
  - Logs: api continues normally.
- **Recovery** — `docker compose start beat`. **Exactly one instance must be running.** Two beats will double-schedule every periodic task.
- **Verified** — ☐

## 5. One scraping source returning 500s

- **Kill** — block a source's outbound DNS, or point its config URL at `httpbin.org/status/500`.
- **Expected** — Consecutive failures tick up for that source. At threshold the circuit transitions `closed → open` and a Slack alert fires. The source is skipped while open; other sources still contribute to consensus. After the cooldown, one probe fires (`open → half_open`, no Slack). If the probe succeeds, `half_open → closed` and a recovery Slack fires. If the probe fails, back to `open`.
- **Observables** —
  - Metric: `koel_scrape_source_fetches_total{source="<slug>",outcome="error"}` rises.
  - Metric: `koel_circuit_transitions_total{source="<slug>",from_status="closed",to_status="open"}` increments.
  - Slack: `:rotating_light: Circuit opened for <slug>` message.
- **Recovery** — Restore the source. Let the probe cycle close the circuit on its own; no manual intervention needed. If you must force-close, delete the Redis key for that source's state.
- **Verified** — ☐

## 6. S3 unreachable during backup

- **Kill** — block S3 endpoint in the firewall, or point `BACKUP_S3_BUCKET` at a non-existent bucket.
- **Expected** — `pg_dump` succeeds; upload fails; temp dir is still cleaned up. Task raises → Celery records failure → Slack backup-failure message fires. **No automatic retry** (avoids spamming S3 + Slack).
- **Observables** —
  - Metric: `koel_backup_runs_total{outcome="failed"}` increments.
  - Slack: `:rotating_light: Backup failed — <error>`.
  - Logs: `backup.failed` with error string.
- **Recovery** — Fix S3 access, then run manually: `celery -A koel.tasks.celery_app call koel.tasks.backup.daily_backup`. Next day's scheduled run will also retry.
- **Verified** — ☐

## 7. SMTP down during magic-link dispatch

- **Kill** — set `SMTP_HOST=smtp.invalid` or block outbound port 587.
- **Expected** — `POST /auth/magic-link` still returns `{"ok": true}` (same shape as success, for enumeration resistance). The `send_magic_link_task` retries with exponential backoff up to 3 times. If all retries fail, the user's link never arrives.
- **Observables** —
  - Metric: failed Celery task count (from celery's own metrics, not Koel's).
  - Logs: `send_magic_link` error traces in worker output.
- **Recovery** — Fix SMTP config. Users who didn't receive a link must re-request.
- **Verified** — ☐

## 8. Slack webhook revoked

- **Kill** — rotate the webhook URL on Slack's side; leave the stale one in `SLACK_WEBHOOK_URL`.
- **Expected** — The Slack client posts, gets a non-2xx, returns `False`. No retry (non-2xx responses are deterministic, not transient). Other systems are unaffected.
- **Observables** —
  - Logs: `notify.slack.*` with `sent=False`.
- **Recovery** — Update `SLACK_WEBHOOK_URL` and redeploy the worker / api.
- **Verified** — ☐

## 9. Disk-full on API host

- **Kill** — `fallocate -l $(df --output=avail / | tail -1)K /tmp/filler`.
- **Expected** — Logs stop writing (if file-backed); `pg_dump` fails with "no space left"; Slack backup-failure fires. API continues serving from existing data until the next write-heavy code path (session creation, usage flush) hits disk.
- **Observables** — Backup-failure Slack; OS-level disk alerts from your host monitoring.
- **Recovery** — Free space (logrotate, clean old backups, scale up volume).
- **Verified** — ☐

## 10. 72-hour soak

- **Setup** — 500 rps on `/rates/current` against a representative dataset (real scraped rates, not seeded). Locust headless, persistent log output.
- **Expected** — P99 latency stable across the window (no slow drift). Memory footprint stable (no leaks). Postgres WAL generation rate stable. No stuck Celery tasks (`celery inspect active` should never show tasks held past their soft timeout).
- **Observables** —
  - Grafana dashboards on `koel_http_request_duration_seconds`, `koel_scrape_pairs_total`, process RSS.
  - Postgres `pg_stat_bgwriter`, `pg_stat_database`.
  - Celery `inspect scheduled`, `inspect active`.
- **Pass criteria** — P99 stays ≤ 20ms; zero error bursts > 0.1% of window traffic; no process restarts.
- **Verified** — ☐

---

## Rehearsal protocol

Before production: work through scenarios 1–8 in order on a staging stack, flipping each `Verified` box as you go. Scenarios 9 and 10 are pre-launch gates — don't flip those until you've run them on prod-equivalent hardware.

For ongoing operations: re-run at least 1–3 (Postgres / Redis / worker) quarterly. Infrastructure changes often, and a rehearsal that was green six months ago may not be today.
