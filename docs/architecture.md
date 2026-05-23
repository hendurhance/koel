# Architecture

Koel is four processes and two datastores:

```
  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
  │   FastAPI   │   │ Celery worker│   │ Celery beat  │
  └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
         │                 │                  │
         │    ┌────────────┴──────────┐       │
         └───▶│        Redis          │◀──────┘
              │  (cache + broker +    │
              │    stream + sessions) │
              └────────────┬──────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │   Postgres     │
                  │ (partitioned)  │
                  └────────────────┘
```

- **FastAPI** serves the read path and the auth / key-management routes. It reads Postgres directly for rates; session lookups go to Redis.
- **Celery worker** runs the write path: scraping jobs, consensus, partition maintenance, usage flushes, daily backups, Slack/SMTP dispatch.
- **Celery beat** fires periodic tasks — dispatch cycles, cross-rate materialization, partition maintenance, usage flushes, daily backup.
- **Postgres** stores currencies, users, keys, current rates, hourly history, raw source observations, and usage events (all range-partitioned where applicable).
- **Redis** is the cache, Celery broker, session store, usage-event stream, and circuit-breaker state store.

---

## Scraping pipeline

Every 60 seconds Beat fires `scrape.dispatch_cycle`, which:

1. Queries `currencies` for pairs whose current-rate row is older than their tier interval (major: 5 min, standard: 1 h, exotic: 6 h).
2. Enqueues one `scrape_pair` per due pair.

Each `scrape_pair` task:

1. Pulls the set of currently callable sources (filtered by circuit state).
2. Uses `curl_cffi` with TLS fingerprint impersonation to fetch each source.
3. Runs `domain.consensus` to pick the agreed rate (drops outliers outside a configurable band).
4. Persists: a raw observation per source, the consensus as the new "current" row, a history row iff the delta vs. last row exceeds 5 bps or an hour has elapsed, and updated circuit state.
5. Emits circuit transitions and Slack alerts for the ones humans care about.

### Why USD pivot?

Storing every direction of every pair is `N * (N-1)` rows per tick. Scraping them all is also `N * (N-1)` HTTP requests. The pivot strategy is:

- Scrape only `USD → X` for each supported X.
- Derive `X → Y` as `(USD → Y) / (USD → X)` and UPSERT it back into the same `exchange_rates_current` table. A Beat task (`materialize_cross_rates_cycle`, every 120s) rebuilds the full cross set from the latest USD rows. Derived rows carry `confidence=null, sources_count=0` so callers can tell them apart from directly-scraped rows.

Accuracy cost is negligible for fiat pairs (spot-checked against known-good data on 20 exotic crosses). Bandwidth and source-load cost drops an order of magnitude.

### Why partitioned history?

`exchange_rates_history` grows ~1 row per pair per hour, across hundreds of pairs. Keeping 24 months of it in a single table makes index maintenance slow and `DROP` expensive. With monthly range partitions:

- Write-locality is a single partition at a time — faster insert, better cache behavior.
- Retention drops are `DROP TABLE partition_name` — instant, no `DELETE … WHERE` scan.
- Partition creation + drop is automated via `koel.tasks.maintenance`.

---

## Circuit breakers

One circuit per source, with three states:

- **closed** — healthy. Scrapes freely.
- **open** — unhealthy. Consecutive failures ≥ threshold. Cooldown timer starts.
- **half_open** — probe after cooldown. One request; success closes, failure re-opens.

Notifications fire for `* → open` (something broke) and `open|half_open → closed` (something recovered). `open → half_open` probe flips are intentionally silent — they're too chatty.

---

## Auth & API keys

- **Users** authenticate by magic link. Token is a hashed, single-use row with a 15-minute TTL.
- **Sessions** are Redis-backed; session ID lives in a cookie, full payload in Redis. Revocation is free.
- **API keys** are grouped under users. Full key is shown once on creation and never stored unhashed (SHA-256 of the key, prefix-only visible in listings).
- **Rate limits** are per-key, enforced via a Redis fixed window (one counter per minute).

---

## Usage tracking

Every authenticated API call produces a `UsageEvent` that the middleware pushes onto a Redis stream (`usage:stream:events`). Every 30 seconds, `usage.flush_usage_events` drains the stream into `api_usage_events` (partitioned by month). The stream is trimmed at 1M entries — if the flusher falls behind enough to hit that, the loss is bounded.

At-most-once-ish per stream entry: we delete from the stream only *after* the Postgres transaction commits. A crash mid-flush replays the batch on the next tick.

---

## Backups

`koel.tasks.backup.daily_backup` runs at 04:00 UTC:

1. Shells out to `pg_dump -Fc` to a private temp dir.
2. Streams the dump to S3 via `aioboto3`.
3. Cleans up the temp dir (on success *and* failure).
4. Dispatches a Slack success or failure message.

No automatic retries — a failed backup is "a human looks," and auto-retrying would spam both S3 and Slack.

---

## Observability

- **Logs** — `structlog` JSON in production, colored console in dev. Every request gets a `request_id` bound on the contextvar, so all log lines emitted inside a request carry the same ID.
- **Metrics** — `prometheus-client` default registry, exposed at `/metrics`. See `koel/observability/metrics.py` for definitions. HTTP metrics label by route template (not raw path), so random-URL scanners can't blow up cardinality.
- **Notifications** — Slack webhook for crawl summaries, circuit transitions, and backup outcomes. Empty `SLACK_WEBHOOK_URL` disables all of it.
