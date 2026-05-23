from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from koel.domain.consensus import ConsensusResult, consensus
from koel.observability.logging import get_logger
from koel.scraping.base import Scraper
from koel.scraping.client import ScrapeClient
from koel.scraping.exceptions import ScraperError
from koel.scraping.registry import get_scraper_cls
from koel.scraping.types import RateReading

ScraperFactory = Callable[[str], type[Scraper]]

log = get_logger("koel.scraping.service")


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """What the dispatcher hands us per source — enough to build and weight a scraper."""

    id: uuid.UUID
    slug: str
    base_url: str
    weight: Decimal
    config: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    source_id: uuid.UUID
    slug: str
    success: bool
    reading: RateReading | None
    error: str | None


@dataclass(frozen=True, slots=True)
class PairOutcome:
    """Everything the dispatcher needs to persist the result of one pair."""

    base: str
    target: str
    consensus: ConsensusResult | None  # None when every source failed
    outcomes: tuple[SourceOutcome, ...]


async def scrape_pair(
    base: str,
    target: str,
    sources: Sequence[SourceSpec],
    client: ScrapeClient,
    *,
    scraper_factory: ScraperFactory = get_scraper_cls,
) -> PairOutcome:
    """Fetch one (base, target) from every supplied source and consensus-combine."""
    if not sources:
        raise ValueError("scrape_pair requires at least one source")

    outcomes = await asyncio.gather(
        *(_run_one(base, target, spec, client, scraper_factory) for spec in sources),
        return_exceptions=False,
    )

    readings = [o.reading for o in outcomes if o.reading is not None]
    if not readings:
        log.warning("scrape.pair.no_readings", base=base, target=target)
        return PairOutcome(base=base, target=target, consensus=None, outcomes=tuple(outcomes))

    weights = {spec.slug: spec.weight for spec in sources}
    result = consensus(readings, weights=weights)
    log.info(
        "scrape.pair.consensus",
        base=base,
        target=target,
        rate=str(result.rate),
        confidence=str(result.confidence),
        sources=result.sources_count,
    )
    return PairOutcome(
        base=base,
        target=target,
        consensus=result,
        outcomes=tuple(outcomes),
    )


async def _run_one(
    base: str,
    target: str,
    spec: SourceSpec,
    client: ScrapeClient,
    factory: ScraperFactory,
) -> SourceOutcome:
    """Build a scraper for a single source and fetch the pair."""
    try:
        cls = factory(spec.slug)
    except KeyError as exc:
        return SourceOutcome(
            source_id=spec.id,
            slug=spec.slug,
            success=False,
            reading=None,
            error=str(exc),
        )

    scraper = _build_scraper(cls, client, spec)
    try:
        reading = await scraper.fetch_single(base, target)
    except ScraperError as exc:
        return SourceOutcome(
            source_id=spec.id,
            slug=spec.slug,
            success=False,
            reading=None,
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # defensive: never let one bad source crash the cycle
        log.exception("scrape.pair.source.crash", source=spec.slug, base=base, target=target)
        return SourceOutcome(
            source_id=spec.id,
            slug=spec.slug,
            success=False,
            reading=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    return SourceOutcome(
        source_id=spec.id,
        slug=spec.slug,
        success=True,
        reading=reading,
        error=None,
    )


def _build_scraper(cls: type[Scraper], client: ScrapeClient, spec: SourceSpec) -> Scraper:
    return cls(client, base_url=spec.base_url, config=dict(spec.config))
