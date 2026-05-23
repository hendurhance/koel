from __future__ import annotations

from koel.scraping.base import Scraper
from koel.scraping.parsing import json_path
from koel.scraping.types import RateReading

_DEFAULT_PATH = "chart.result.0.meta.regularMarketPrice"


class YahooFinanceScraper(Scraper):
    slug = "yahoo_finance"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/v8/finance/chart/{base}{target}=X"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        data, latency_ms = await self._get_json(self._url_for(base, target))
        raw = json_path(data, self.config.get("json_path", _DEFAULT_PATH))
        return self._reading(base, target, raw, latency_ms)
