from __future__ import annotations

from koel.scraping.base import Scraper
from koel.scraping.parsing import extract_first_number, select_attr
from koel.scraping.types import RateReading


class MarketWatchScraper(Scraper):
    slug = "marketwatch"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/investing/currency/{base.lower()}{target.lower()}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        html, latency_ms = await self._get_text(self._url_for(base, target))
        raw = select_attr(html, 'meta[name="price"]', "content")  # e.g. "€0.8618"
        return self._reading(base, target, extract_first_number(raw), latency_ms)
