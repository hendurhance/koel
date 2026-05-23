from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from koel.observability.logging import get_logger
from koel.scraping.client import ScrapeClient
from koel.scraping.exceptions import ScraperError
from koel.scraping.types import RateReading

log = get_logger("koel.scraping")

Mode = Literal["pair", "bulk"]


class Scraper(ABC):
    slug: ClassVar[str]
    mode: ClassVar[Mode] = "pair"

    def __init__(self, client: ScrapeClient, *, base_url: str, config: dict[str, Any]) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.config = config

    @property
    def _impersonate(self) -> str:
        return str(self.config.get("impersonate", "chrome124"))

    async def _get_text(self, url: str) -> tuple[str, int]:
        return await self.client.get_text(url, impersonate=self._impersonate)

    async def _get_json(self, url: str) -> tuple[Any, int]:
        return await self.client.get_json(url, impersonate=self._impersonate)

    async def fetch_rates(self, base: str, targets: Sequence[str]) -> list[RateReading]:
        """Default implementation: fan out `_fetch_one` across targets concurrently.
        Bulk scrapers override this entirely."""
        results = await asyncio.gather(
            *(self._fetch_one(base, t) for t in targets),
            return_exceptions=True,
        )
        readings: list[RateReading] = []
        for target, r in zip(targets, results, strict=True):
            if isinstance(r, RateReading):
                readings.append(r)
            else:
                log.warning(
                    "scrape.pair.failed",
                    source=self.slug,
                    base=base,
                    target=target,
                    error=str(r),
                )
        return readings

    async def fetch_single(self, base: str, target: str) -> RateReading:
        """Fetch exactly one pair, propagating scraper exceptions to the caller.

        The dispatcher uses this so it can categorize failures (``BlockedError``
        vs ``NetworkError`` vs ``ParseError``) and update per-source health.
        ``fetch_rates`` is still the right entry point for multi-target bulk
        scrapers — this helper is for the per-pair dispatcher path.
        """
        if self.mode == "pair":
            return await self._fetch_one(base, target)
        readings = await self.fetch_rates(base, [target])
        for reading in readings:
            if reading.base == base and reading.target == target:
                return reading
        raise ScraperError(f"{self.slug} returned no reading for {base}->{target}")

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        """Override in single-pair scrapers. Bulk scrapers never call this."""
        raise NotImplementedError(f"{self.slug} must override _fetch_one or fetch_rates")

    @abstractmethod
    def _url_for(self, base: str, target: str | None = None) -> str:
        """Build the URL for this source. `target` is None for bulk scrapers."""

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=UTC)

    def _reading(self, base: str, target: str, rate: Any, latency_ms: int) -> RateReading:
        """Convenience: build a RateReading with common fields filled in.
        Subclasses that want different source_slug can override."""
        from koel.scraping.parsing import parse_decimal

        return RateReading(
            source_slug=self.slug,
            base=base,
            target=target,
            rate=parse_decimal(rate),
            fetched_at=self._now(),
            latency_ms=latency_ms,
        )


# Re-export for convenience.
__all__ = ["Mode", "Scraper", "ScraperError"]
