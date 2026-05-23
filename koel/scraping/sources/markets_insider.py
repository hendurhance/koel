from __future__ import annotations

from koel.scraping.base import Scraper
from koel.scraping.parsing import parse_decimal, select_first_text
from koel.scraping.types import RateReading

_SELECTORS = [".price-section__current-value", ".price-section__values .price-section__current-value"]


class MarketsInsiderScraper(Scraper):
    slug = "markets_insider"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/currencies/{base.lower()}-{target.lower()}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        html, latency_ms = await self._get_text(self._url_for(base, target))
        # The element often carries a currency suffix, e.g. "0.8617 EUR".
        raw = select_first_text(html, _SELECTORS).split()[0]
        return self._reading(base, target, parse_decimal(raw), latency_ms)
