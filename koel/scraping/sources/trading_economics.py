from __future__ import annotations

from collections.abc import Sequence

from selectolax.parser import HTMLParser

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import parse_decimal
from koel.scraping.types import RateReading


class TradingEconomicsScraper(Scraper):
    slug = "trading_economics"
    mode = "bulk"

    def _url_for(self, base: str, target: str | None = None) -> str:
        return f"{self.base_url}/currencies?base={base}"

    async def fetch_rates(self, base: str, targets: Sequence[str]) -> list[RateReading]:
        html, latency_ms = await self._get_text(self._url_for(base))
        tree = HTMLParser(html)

        table = tree.css_first("table.table-heatmap")
        if table is None:
            raise ParseError("trading_economics: heatmap table not found")

        target_set = {t.upper() for t in targets}
        fetched_at = self._now()
        readings: list[RateReading] = []

        for row in table.css("tr[data-symbol]"):
            symbol = (row.attributes.get("data-symbol") or "").split(":")[0]
            if not symbol.startswith(base):
                continue
            code = symbol[len(base) :]
            if code not in target_set:
                continue
            cells = row.css("td")
            if len(cells) < 2:
                continue
            try:
                rate = parse_decimal(cells[1].text(strip=True))
            except ParseError:
                continue
            readings.append(
                RateReading(
                    source_slug=self.slug,
                    base=base,
                    target=code,
                    rate=rate,
                    fetched_at=fetched_at,
                    latency_ms=latency_ms,
                )
            )
        return readings
