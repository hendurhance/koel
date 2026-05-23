from koel.scraping.base import Scraper
from koel.scraping.parsing import json_path
from koel.scraping.types import RateReading


class HexarateScraper(Scraper):
    slug = "hexarate"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/api/rates/latest/{base}?target={target}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        data, latency_ms = await self._get_json(self._url_for(base, target))
        raw = json_path(data, self.config.get("json_path", "data.mid"))
        return self._reading(base, target, raw, latency_ms)
