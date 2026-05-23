from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.parsing import parse_decimal
from koel.scraping.types import RateReading


class ForbesScraper(Scraper):
    slug = "forbes"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        return (
            f"{self.base_url}/advisor/money-transfer/currency-converter/"
            f"{base.lower()}-{target.lower()}/?amount=1"
        )

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        html, latency_ms = await self._get_text(self._url_for(base, target))
        tree = HTMLParser(html)

        body = tree.body.text(deep=True, separator=" ", strip=True) if tree.body else ""
        pattern = re.compile(
            rf"1\s*{re.escape(base)}\s*=\s*([\d.,]+)\s*{re.escape(target)}",
            re.IGNORECASE,
        )
        match = pattern.search(body)
        if not match:
            raise ParseError("forbes: conversion text not found")

        rate = parse_decimal(match.group(1))
        return self._reading(base, target, rate, latency_ms)
