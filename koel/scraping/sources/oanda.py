from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from koel.scraping.base import Scraper
from koel.scraping.exceptions import ParseError
from koel.scraping.types import RateReading


class OandaScraper(Scraper):
    slug = "oanda"
    mode = "pair"

    def _url_for(self, base: str, target: str | None = None) -> str:
        assert target is not None
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=3)
        return (
            f"{self.base_url}/cc-api/currencies?"
            f"base={base}&quote={target}&data_type=chart"
            f"&start_date={start.isoformat()}&end_date={today.isoformat()}"
        )

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        data, latency_ms = await self._get_json(self._url_for(base, target))
        # API returns either `response` (singular, 2026) or `responses` (legacy).
        entries = data.get("response") or data.get("responses") or []
        if not entries:
            raise ParseError("oanda: empty response")
        latest = entries[-1]
        try:
            bid = Decimal(str(latest["average_bid"]))
            ask = Decimal(str(latest["average_ask"]))
        except (KeyError, ValueError) as exc:
            raise ParseError(f"oanda: malformed entry: {latest}") from exc
        mid = (bid + ask) / 2
        return self._reading(base, target, mid, latency_ms)
