from __future__ import annotations

import json

from selectolax.parser import HTMLParser

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.types import RateReading


class FxEmpireScraper(Scraper):
    slug = "fx_empire"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/currencies/{base.lower()}-{target.lower()}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        html, latency_ms = await self._get_text(self._url_for(base, target))
        tree = HTMLParser(html)

        script = tree.css_first("script#__NEXT_DATA__")
        if script is None:
            raise ParseError("fx_empire: __NEXT_DATA__ not found")

        try:
            data = json.loads(script.text())
        except json.JSONDecodeError as exc:
            raise ParseError(f"fx_empire: __NEXT_DATA__ JSON invalid: {exc}") from exc

        instrument = f"{base.lower()}-{target.lower()}"
        try:
            queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        except (KeyError, TypeError) as exc:
            raise ParseError("fx_empire: unexpected __NEXT_DATA__ shape") from exc

        for query in queries:
            state = query.get("state") or {}
            payload = state.get("data") or {}
            if payload.get("statusCode") != 200:
                continue
            prices = (payload.get("data") or {}).get("prices") or {}
            entry = prices.get(instrument)
            if entry and entry.get("last") is not None:
                return self._reading(base, target, entry["last"], latency_ms)

        raise ParseError(f"fx_empire: no price entry for {instrument}")
