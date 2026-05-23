from __future__ import annotations

import re
from collections.abc import Sequence

from selectolax.parser import HTMLParser

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import parse_decimal
from koel.scraping.types import RateReading


class ExchangeRatesOrgScraper(Scraper):
    slug = "exchange_rates_org"
    mode = "bulk"

    def _url_for(self, base: str, target: str | None = None) -> str:
        slug_map: dict[str, str] = self.config.get("base_name_slug_map", {})
        name_slug = slug_map.get(base)
        if name_slug is None:
            raise ParseError(f"exchange_rates_org: no base_name_slug for {base}")
        return f"{self.base_url}/{name_slug}-{base}-currency-table.html"

    async def fetch_rates(self, base: str, targets: Sequence[str]) -> list[RateReading]:
        html, latency_ms = await self._get_text(self._url_for(base))
        tree = HTMLParser(html)

        rows = tree.css("tr.colone, tr.coltwo")
        if not rows:
            raise ParseError("exchange_rates_org: no rate rows found")

        target_set = {t.upper() for t in targets}
        fetched_at = self._now()
        readings: list[RateReading] = []

        for row in rows:
            cells = row.css("td")
            if len(cells) < 5:
                continue
            link = cells[3].css_first("a")
            if link is None:
                continue
            href = link.attributes.get("href") or ""
            match = re.search(r"([A-Z]{3})", href)
            code = match.group(1) if match else link.text(strip=True).upper()
            if code not in target_set:
                continue
            rate_text = cells[4].text(strip=True)
            try:
                rate = parse_decimal(rate_text)
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
