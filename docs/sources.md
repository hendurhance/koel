# Scrape sources

Koel pulls rates from many independent sources and forms a consensus (median +
confidence) per pair. Each source is one row in the `sources` table (seeded from
`koel/data/sources.json`) plus one scraper class in `koel/scraping/sources/`,
wired into `koel/scraping/registry.py`.

## How a source is defined

`sources.json` entry:

| field | meaning |
|---|---|
| `slug` | stable id; must match `Scraper.slug` and a key in `registry.SCRAPERS` |
| `name` | display name |
| `base_url` | scheme + host; the scraper appends the path |
| `weight` | consensus weight (higher = more trusted) |
| `is_active` | `false` = **shelved**: registered + seeded but never dispatched |
| `config` | free-form; `mode` (`pair`/`bulk`), `impersonate`, source-specific hints |

`is_active=false` is the shelf: the row exists, the scraper is importable and
unit-tested, but `dispatch_due_currencies` skips it. Flip it to `true` (and
re-seed, or just `UPDATE sources SET is_active=true WHERE slug=...`) to enable.
Re-seeding never flips `is_active` back — `seed_sources` deliberately leaves it
out of the `on_conflict_do_update`, so operator toggles stick.

## HTTP + parsing model

- Fetch with `curl_cffi` impersonating a real browser TLS/HTTP-2 fingerprint
  (`config.impersonate`, default `chrome124`) — reputable finance sites gate
  plain HTTP clients, so impersonation is what gets us a real response.
- `mode="pair"` scrapers override `_fetch_one(base, target)`; `mode="bulk"`
  scrapers override `fetch_rates(base, targets)` and filter one table.
- Extract via `selectolax` CSS selectors (`select_first_text`, `select_attr`)
  or a regex over body text; normalise with `parse_decimal`.

## Shelved sources (added, `is_active=false`)

Five reputable-brand sources. Each was **probed live against USD→EUR on
2026-05-23** (`uv run python scripts/probe_sources.py <slug>`) and returned the
correct rate. They're shelved so an operator opts in; the per-source circuit
breaker keeps a flaky one from poisoning consensus.

### Yahoo Finance — `yahoo_finance`
- **URL:** `https://query1.finance.yahoo.com/v8/finance/chart/{BASE}{TARGET}=X` (e.g. `USDEUR=X`)
- **Crawl:** JSON — `chart.result[0].meta.regularMarketPrice`.
- **Notes:** Yahoo's *own* chart endpoint. We use it because the HTML quote page renders the price client-side (the static page's only `regularMarketPrice` is the market-summary index strip — see "rejected" below).

### Investing.com — `investing`
- **URL:** `https://www.investing.com/currencies/{base}-{target}` (lowercase, e.g. `usd-eur`)
- **Crawl:** `[data-test="instrument-price-last"]`.
- **Notes:** Cloudflare-fronted; `curl_cffi` impersonation gets through but expect intermittent challenges (circuit breaker absorbs them).

### MarketWatch (Dow Jones) — `marketwatch`
- **URL:** `https://www.marketwatch.com/investing/currency/{base}{target}` (lowercase, e.g. `usdeur`)
- **Crawl:** `<meta name="price" content="€0.8618">` (paired with `<meta name="priceCurrency">`). Read the `content` attribute and strip the currency glyph (`extract_first_number`). The on-page `<bg-quote>` elements are mover widgets, *not* this pair's rate — don't use them.

### Markets Insider (Business Insider) — `markets_insider`
- **URL:** `https://markets.businessinsider.com/currencies/{base}-{target}` (lowercase, e.g. `usd-eur`)
- **Crawl:** `.price-section__current-value`. The text may carry a currency suffix (`"0.8619 EUR"`); take the first whitespace token.

### Financial Times — `ft`
- **URL:** `https://markets.ft.com/data/currencies/tearsheet/summary?s={BASE}{TARGET}` (e.g. `USDEUR`)
- **Crawl:** first `.mod-ui-data-list__value` span (the latest price).

### Evaluated and rejected: Google Finance
Prototyped and **probed live, then dropped** — Google Finance does not render
the rate into static HTML at all (no `data-last-price`, no `YMlKec` node); the
page hydrates entirely via JS (`AF_initDataCallback` blobs). It would need a
JS-rendering fetch (e.g. Playwright), which is out of scope for the curl_cffi
pipeline. WSJ market-data was also tried and returns `401` to impersonated
fetches.

> Yahoo Finance had the same HTML-rendering problem (its static page's only
> `regularMarketPrice` is the market-summary index strip), which is why
> `yahoo_finance` above uses Yahoo's chart **API** instead of scraping the page.

## Why these (and not free aggregator APIs)

We deliberately picked reputable, brand-name finance sites scraped via HTML
rather than free aggregator JSON APIs (frankfurter, open.er-api, jsDelivr
currency-api, vatcomply, fxratesapi, …). Aggregators mostly re-publish the same
ECB/central-bank feed, so adding several would inflate the source count without
adding independent signal — and they aren't "sources" an operator would vouch
for. The HTML brands above are independent price discoveries.

## Adding another source

1. New file in `koel/scraping/sources/` subclassing `Scraper`.
2. Register it in `koel/scraping/registry.py`.
3. Add a `sources.json` entry (set `is_active=false` to shelve it first).
4. Add a contract test with canned markup (see `tests/unit/scraping/`).
5. `make openapi` is unaffected; just re-seed (`koel db seed`).
