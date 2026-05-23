from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

MOVE_THRESHOLD_BP = Decimal("5")  # 5 basis points = 0.05%.
HEARTBEAT_SECONDS = 3600  # 1 hour.


@dataclass(frozen=True, slots=True)
class Anchor:
    rate: Decimal
    observed_at: datetime


def should_write_history(
    new_rate: Decimal,
    new_observed_at: datetime,
    previous: Anchor | None,
    *,
    move_threshold_bp: Decimal = MOVE_THRESHOLD_BP,
    heartbeat: timedelta = timedelta(seconds=HEARTBEAT_SECONDS),
) -> bool:
    """Return True if the new reading warrants a history row."""
    if previous is None:
        return True
    if new_rate <= 0:
        raise ValueError("new_rate must be positive")

    if _elapsed(new_observed_at, previous.observed_at) >= heartbeat:
        return True

    move_bp = abs(new_rate - previous.rate) / previous.rate * Decimal(10_000)
    return move_bp >= move_threshold_bp


def _elapsed(new: datetime, old: datetime) -> timedelta:
    """Handle either direction — caller order shouldn't matter for elapsed time."""
    if new >= old:
        return new - old
    return old - new
