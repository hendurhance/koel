from __future__ import annotations

import re
from collections.abc import Sequence

from selectolax.parser import HTMLParser

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import parse_decimal
from koel.scraping.types import RateReading


class XratesScraper(Scraper):
    slug = "xrates"
    mode = "bulk"

    def _url_for(self, base: str, target: str | None = None) -> str:
        return f"{self.base_url}/table/?from={base}&amount=1"

    async def fetch_rates(self, base: str, targets: Sequence[str]) -> list[RateReading]:
        html, latency_ms = await self._get_text(self._url_for(base))
        tree = HTMLParser(html)

        table = tree.css_first("table.tablesorter.ratesTable")
        if table is None:
            raise ParseError("xrates: rates table not found")

        target_set = {t.upper() for t in targets}
        fetched_at = self._now()
        readings: list[RateReading] = []

        for row in table.css("tr"):
            cells = row.css("td")
            if len(cells) < 2:
                continue
            link = cells[1].css_first("a")
            if link is None:
                continue
            href = link.attributes.get("href") or ""
            match = re.search(r"to=([A-Z]{3})", href)
            if match is None:
                continue
            code = match.group(1)
            if code not in target_set:
                continue
            try:
                rate = parse_decimal(link.text(strip=True))
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
