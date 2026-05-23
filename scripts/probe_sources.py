from __future__ import annotations

import asyncio
import json
import sys
import time
from importlib import resources

from koel.scraping.client import ScrapeClient
from koel.scraping.registry import SCRAPERS

SOURCES = json.loads(resources.files("koel.data").joinpath("sources.json").read_text())
SOURCE_BY_SLUG = {s["slug"]: s for s in SOURCES}


async def probe(slug: str, base: str = "USD", target: str = "EUR") -> None:
    source = SOURCE_BY_SLUG.get(slug)
    cls = SCRAPERS.get(slug)
    if source is None:
        print(f"  {slug:<22} NO CONFIG in sources.json")
        return
    if cls is None:
        print(f"  {slug:<22} NO SCRAPER class registered")
        return

    started = time.perf_counter()
    try:
        async with ScrapeClient() as client:
            scraper = cls(client, base_url=source["base_url"], config=source["config"])
            readings = await scraper.fetch_rates(base, [target])
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        print(f"  {slug:<22} FAIL ({elapsed}ms): {type(exc).__name__}: {exc}")
        return

    elapsed = int((time.perf_counter() - started) * 1000)
    if not readings:
        print(f"  {slug:<22} EMPTY ({elapsed}ms)")
        return
    r = readings[0]
    print(f"  {slug:<22} OK   {base}->{target} = {r.rate:.6f}  ({elapsed}ms)")


async def main() -> None:
    slugs = sys.argv[1:] or [s["slug"] for s in SOURCES]
    print(f"Probing {len(slugs)} source(s) for USD -> EUR\n")
    for slug in slugs:
        await probe(slug)


if __name__ == "__main__":
    asyncio.run(main())
