# API reference

Base URL: whatever you expose the FastAPI app on. Locally that's `http://localhost:8000`.

All rate / currency / source endpoints require an API key passed as `X-API-Key: <key>`. Auth / key-management endpoints use the session cookie (`koel_session`) issued by the magic-link flow.

---

## Health

### `GET /healthz`

Liveness — always returns 200 when the process is up.

```json
{ "status": "ok", "version": "1.0.0" }
```

### `GET /readyz`

Readiness — probes Postgres and Redis. Returns `503` if either is unreachable.

```json
{ "status": "ok", "checks": { "database": "ok", "redis": "ok" } }
```

### `GET /metrics`

Prometheus exposition format. Not authenticated — run it behind a cluster firewall.

---

## Auth

### `POST /auth/request-link`

```json
{ "email": "you@example.com" }
```

Returns `202 Accepted` with `{"delivered": true}`. The response is identical whether the email is known or not, to avoid enumeration. A per-email cooldown (`REQUEST_LINK_COOLDOWN_SECONDS`) rate-limits repeat requests; throttled requests return the same payload.

### `GET /auth/verify?token=<token>`

Consumes a magic-link token, creates-or-fetches the user, starts a Redis-backed session, and sets a session cookie (`koel_session`). Returns the authenticated user payload.

```json
{ "user": { "id": "uuid", "email": "you@example.com", "role": "user", "is_active": true } }
```

If the token is unknown, already consumed, or expired, returns `400`.

### `POST /auth/logout`

Invalidates the current session (revokes the Redis entry and clears the cookie).

### `GET /auth/me`

Returns the currently authenticated user payload. `401` when no valid session cookie is present.

---

## Keys

Keys live under *groups*. A group is just a named bucket for keys so you can rotate, revoke, or track usage at a coarser grain. All `/keys/*` endpoints are session-authenticated and scoped to the caller — you never see or touch another user's groups.

### `GET /keys/groups`

List your groups.

```json
{
  "groups": [
    { "id": "uuid", "name": "dev", "description": "local dev", "keys_count": 1, "created_at": "…" }
  ]
}
```

### `POST /keys/groups`

```json
{ "name": "dev", "description": "local dev" }
```

Returns the new `GroupInfo` with `"keys_count": 0`.

### `GET /keys/groups/{group_id}`

Fetch one group. `404` if you don't own it (same response as "doesn't exist" — no enumeration).

### `DELETE /keys/groups/{group_id}`

`204` on success. Cascades to all keys in the group.

### `GET /keys/groups/{group_id}/keys`

List the keys in a group.

```json
{
  "keys": [
    {
      "id": "uuid",
      "group_id": "uuid",
      "name": "dev-primary",
      "key_prefix": "frgir067",
      "scopes": ["rates:read"],
      "rate_limit_per_min": 1000,
      "is_active": true,
      "last_used_at": null,
      "expires_at": null,
      "revoked_at": null,
      "created_at": "…"
    }
  ]
}
```

### `POST /keys/groups/{group_id}/keys`

```json
{
  "name": "dev-primary",
  "scopes": ["rates:read"],
  "rate_limit_per_min": 1000,
  "expires_at": null
}
```

Only `name` is required; `scopes` defaults to `["rates:read"]`, `rate_limit_per_min` to the configured default.

Response (the **full key is only shown here, never again**):

```json
{
  "key": "koel_frgir067_<rest_of_secret>",
  "info": { "id": "uuid", "key_prefix": "frgir067", "…": "…" }
}
```

### `DELETE /keys/keys/{key_id}`

Revokes the key. Subsequent requests with it return `401`.

---

## Rates

### `GET /rates/current?base=<code>[&target=<code>]`

Two shapes depending on whether `target` is supplied.

Single pair (`target` given):

```json
{
  "base": "USD",
  "target": "EUR",
  "rate": "0.851680000000",
  "confidence": "1.000",
  "sources_count": 9,
  "observed_at": "2026-04-22T00:23:46.514108+00:00"
}
```

All targets (`target` omitted):

```json
{
  "base": "USD",
  "rates": [
    { "target": "EUR", "rate": "0.851680", "confidence": "1.000", "sources_count": 9, "observed_at": "…" },
    { "target": "GBP", "rate": "0.751200", "confidence": "1.000", "sources_count": 8, "observed_at": "…" }
  ]
}
```

Non-USD bases are served by a row that a Beat task (`materialize_cross_rates_cycle`, every 120s) UPSERTs into the same `exchange_rates_current` table, derived as `X→Y = USD→Y / USD→X`. Derived rows report `confidence: null` and `sources_count: 0` so clients can tell them apart from directly-scraped rows.

### `GET /rates/history?base=<code>&target=<code>[&since=<ISO>&until=<ISO>&limit=<n>]`

Hourly-anchored time series. Each row is either an anchor (one per hour regardless) or a delta row (change ≥ 5 bps). `since`/`until` are inclusive ISO-8601 bounds; `since` defaults to 24 hours ago when omitted. `limit` caps the number of points returned (default `500`, max `10000`).

```json
{
  "base": "USD",
  "target": "EUR",
  "points": [
    { "rate": "0.920100", "confidence": "1.000", "sources_count": 8, "observed_at": "2026-04-20T00:00:00+00:00" },
    { "rate": "0.920800", "confidence": "1.000", "sources_count": 8, "observed_at": "2026-04-20T01:00:00+00:00" }
  ]
}
```

### `GET /rates/convert?from=<code>&to=<code>&amount=<number>`

Converts an amount between two currencies at the current rate. All three params are required; `amount` accepts a number or numeric string. Monetary values come back as strings.

```json
{
  "from": "USD",
  "to": "EUR",
  "amount": "100",
  "rate": "0.851680000000",
  "result": "85.168000000000",
  "observed_at": "2026-04-22T00:23:46.514108+00:00"
}
```

---

## Currencies

### `GET /currencies`

Lists active currencies (inactive ones are filtered server-side).

```json
{
  "currencies": [
    { "code": "USD", "name": "United States dollar", "symbol": "$",  "decimal_digits": 2, "tier": "major" },
    { "code": "EUR", "name": "Euro",                  "symbol": "€",  "decimal_digits": 2, "tier": "major" }
  ]
}
```

`tier` is one of `major`, `standard`, `exotic` — it drives how often each currency is scraped.

---

## Sources

### `GET /sources`

Lists configured scrape sources with their current circuit-breaker health. `health` is `null` for sources that haven't been probed yet.

```json
{
  "sources": [
    {
      "slug": "xrates",
      "name": "x-rates.com",
      "weight": "1.000",
      "is_active": true,
      "health": {
        "circuit_state": "closed",
        "consecutive_failures": 0,
        "total_requests": 1240,
        "total_failures": 3,
        "avg_latency_ms": "147.200",
        "last_success_at": "2026-04-22T00:29:46+00:00",
        "last_failure_at": "2026-04-20T11:02:18+00:00"
      }
    }
  ]
}
```

`circuit_state` is one of `closed`, `open`, `half_open`. See [`docs/architecture.md`](architecture.md#circuit-breakers).

---

## Usage

### `GET /usage/summary`

Query params: `group_id` (optional), `key_id` (optional), `from`, `to` (ISO-8601 datetimes). Default window: 30 days. Max: 180 days. The response always includes both a per-day and a per-endpoint breakdown.

```json
{
  "from": "2026-03-22T00:00:00+00:00",
  "to": "2026-04-21T00:00:00+00:00",
  "by_day": [
    { "date": "2026-04-20", "requests": 1240, "errors": 7, "avg_response_time_ms": "12.4", "total_bytes": 492000 }
  ],
  "by_endpoint": [
    { "endpoint": "/rates/current", "requests": 1180, "errors": 2, "avg_response_time_ms": "8.1", "total_bytes": 470000 }
  ]
}
```

Scoping is enforced server-side: you can only read usage for keys in groups you own.

---

## Admin

Admin-only: requires a session cookie for a user with `role: admin`. Non-admins get `403`.

### `GET /admin/audit?[limit=<n>&action=<action>]`

Most-recent-first audit entries. `limit` defaults to `50` (max `200`); `action` filters to a single action (e.g. `apikey.create`, `user.promote`).

```json
{
  "entries": [
    {
      "action": "apikey.create",
      "actor_user_id": "uuid",
      "subject_type": "apikey",
      "subject_id": "uuid",
      "metadata": { "group_id": "uuid", "prefix": "frgir067", "scopes": ["rates:read"] },
      "ip_address": "203.0.113.7",
      "occurred_at": "2026-04-22T00:29:46+00:00"
    }
  ]
}
```

---

## Errors

All 4xx / 5xx responses follow a consistent shape:

```json
{ "detail": "Unauthorized" }
```

Validation errors from Pydantic use FastAPI's default shape (`{"detail": [{"loc": […], "msg": "…", "type": "…"}]}`).
