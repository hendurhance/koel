from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import parse_decimal
from koel.scraping.types import RateReading


class XeScraper(Scraper):
    slug = "xe"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return f"{self.base_url}/currencyconverter/convert/?Amount=1&From={base}&To={target}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        html, latency_ms = await self._get_text(self._url_for(base, target))
        tree = HTMLParser(html)
        body = tree.body.text(deep=True, separator=" ", strip=True) if tree.body else ""

        pattern = re.compile(
            rf"1(?:\.0+)?\s*{re.escape(base)}\s*=\s*([\d.,]+)\s*{re.escape(target)}\b",
            re.IGNORECASE,
        )
        match = pattern.search(body)
        if not match:
            raise ParseError("xe: rate pattern not found")

        return self._reading(base, target, parse_decimal(match.group(1)), latency_ms)
