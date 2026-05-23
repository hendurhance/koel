from __future__ import annotations

from collections.abc import Sequence

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import parse_decimal
from koel.scraping.types import RateReading


class FloatRatesScraper(Scraper):
    slug = "floatrates"
    mode = "bulk"

    def _url_for(self, base: str, target: str | None = None) -> str:
        return f"{self.base_url}/daily/{base.lower()}.json"

    async def fetch_rates(self, base: str, targets: Sequence[str]) -> list[RateReading]:
        data, latency_ms = await self._get_json(self._url_for(base))
        if not isinstance(data, dict):
            raise ParseError("floatrates: unexpected response type")

        target_set = {t.upper() for t in targets}
        fetched_at = self._now()
        readings: list[RateReading] = []

        for target in target_set:
            entry = data.get(target.lower())
            if not entry or "rate" not in entry:
                continue
            try:
                rate = parse_decimal(entry["rate"])
            except ParseError:
                continue
            readings.append(
                RateReading(
                    source_slug=self.slug,
                    base=base,
                    target=target,
                    rate=rate,
                    fetched_at=fetched_at,
                    latency_ms=latency_ms,
                )
            )
        return readings
