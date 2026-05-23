from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RateReading:
    """One (source, pair, timestamp) measurement. Domain type — independent
    of the DB ORM so scrapers can be tested without a database."""

    source_slug: str
    base: str
    target: str
    rate: Decimal
    fetched_at: datetime
    latency_ms: int
