from __future__ import annotations

from koel.scraping.base import Scraper
from koel.scraping.parsing import parse_decimal, select_first_text
from koel.scraping.types import RateReading


class FtScraper(Scraper):
    slug = "ft"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/data/currencies/tearsheet/summary?s={base}{target}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        html, latency_ms = await self._get_text(self._url_for(base, target))
        raw = select_first_text(html, [".mod-ui-data-list__value"])
        return self._reading(base, target, parse_decimal(raw), latency_ms)
