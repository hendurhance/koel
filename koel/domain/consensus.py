from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from koel.scraping.types import RateReading

# Consensus tuning. These are intentionally conservative defaults; tune from
# operational data once we've shipped.
DEFAULT_EPSILON = Decimal("0.005")  # 50bp — "agreeing" means within 0.5%.
DIVERSITY_TARGET = 3  # 3+ independent sources = full diversity credit.


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    rate: Decimal
    confidence: Decimal
    sources_count: int
    sources_used: tuple[str, ...]


def consensus(
    readings: Iterable[RateReading],
    *,
    weights: Mapping[str, Decimal] | None = None,
    epsilon: Decimal = DEFAULT_EPSILON,
) -> ConsensusResult:
    """Combine readings into a single rate + confidence.

    Raises ValueError if no readings provided. Readings must all share the
    same (base, target); the caller guarantees this.
    """
    readings_list = list(readings)
    if not readings_list:
        raise ValueError("consensus requires at least one reading")

    weights = weights or {}
    weighted = [(r, weights.get(r.source_slug, Decimal("1"))) for r in readings_list]
    rate = _weighted_median(weighted)

    agreement = _agreement(readings_list, rate, epsilon)
    diversity = min(Decimal(1), Decimal(len(readings_list)) / Decimal(DIVERSITY_TARGET))
    confidence = (agreement * diversity).quantize(Decimal("0.001"))

    return ConsensusResult(
        rate=rate,
        confidence=confidence,
        sources_count=len(readings_list),
        sources_used=tuple(r.source_slug for r in readings_list),
    )


def _weighted_median(items: list[tuple[RateReading, Decimal]]) -> Decimal:
    """Weighted median: smallest value at or above which cumulative weight
    reaches half the total. For equal weights this is the classic median."""
    sorted_items = sorted(items, key=lambda it: it[0].rate)
    total = sum((w for _, w in sorted_items), Decimal(0))
    threshold = total / 2
    cumulative = Decimal(0)
    for reading, weight in sorted_items:
        cumulative += weight
        if cumulative >= threshold:
            return reading.rate
    # Unreachable — sum of weights is positive by construction.
    return sorted_items[-1][0].rate


def _agreement(readings: list[RateReading], centre: Decimal, epsilon: Decimal) -> Decimal:
    """Fraction of readings whose rate is within `epsilon` (relative) of centre."""
    tolerance = centre * epsilon
    within = sum(1 for r in readings if abs(r.rate - centre) <= tolerance)
    return Decimal(within) / Decimal(len(readings))
