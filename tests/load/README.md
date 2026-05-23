# Load tests

Goal: prove P99 `/rates/current` stays under 20ms at 500 rps.

## Prerequisites

1. A running Koel stack (Docker or local).
2. At least one API key. Mint one via the `/auth` + `/keys` flow; for an unthrottled load-test key, set a high `rate_limit_per_min` (up to 100000) when creating it (`POST /keys/groups/{id}/keys`).
3. `locust` installed (`uv pip install locust` or `uv sync --extra load`).

## Running

```bash
export KOEL_API_KEY=koel_xxxxxxxxxxxxxxxx
uv run locust -f tests/load/locustfile.py \
    --host http://localhost:8000 \
    --users 500 --spawn-rate 50 \
    --run-time 5m --headless \
    --csv build/loadtest
```

`--headless` runs without the web UI and writes CSV results to `build/loadtest_*.csv`. Drop `--headless` to use the web dashboard at http://localhost:8089.

## Reading results

Look at `build/loadtest_stats.csv`:

| Column | Meaning |
|---|---|
| `Request Count` | Total requests in the window |
| `Failure Count` | 4xx/5xx responses |
| `Average Response Time` | Mean ms |
| `99%` | P99 in ms — **this is the gate** |
| `Requests/s` | Observed throughput |

Pass criteria:
- `99%` on `/rates/current` ≤ 20.
- `Failure Count` on `/rates/current` ≤ 0.1% of total.
- No sustained error bursts (check `build/loadtest_failures.csv`).

## Tuning the load

- `--users 500` sets the target concurrency. Start at 100, ramp up.
- `--spawn-rate 50` is new users/sec during ramp. Keep low enough that you observe steady state, not ramp transients.
- `--run-time 5m` — at least 5 min so P99 is stable.
- For a 72h soak: `--run-time 72h` on a persistent host; monitor Postgres WAL + disk + connection pool separately.

## Troubleshooting

- All failures on `/rates/current`: API key missing or revoked. Check `KOEL_API_KEY`.
- 429s: key rate limit kicked in. Create a higher-limit key for load tests.
- P99 > 20ms: check `/metrics` for `koel_http_request_duration_seconds` bucket distribution, and Postgres `pg_stat_activity` for slow queries.
