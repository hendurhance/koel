from __future__ import annotations

import uuid
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from koel.config import get_settings
from koel.domain.circuit import (
    COOLDOWN,
    CircuitState,
    allow_call,
    on_failure,
    on_success,
)
from koel.domain.delta import Anchor, should_write_history
from koel.scraping.service import PairOutcome, SourceSpec

USD = "USD"


@dataclass(frozen=True, slots=True)
class DuePair:
    base_code: str
    target_code: str


@dataclass(frozen=True, slots=True)
class HealthTransition:
    """Captured by ``_update_source_health`` when a call flips the circuit state.

    Surfaces back through ``persist_pair_outcome`` so the Celery task layer
    can fan out Slack alerts without the DB layer importing ``celery``.
    """

    source_id: uuid.UUID
    source_slug: str
    from_status: str
    to_status: str
    consecutive_failures: int
    opened_at: datetime | None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": str(self.source_id),
            "source_slug": self.source_slug,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "consecutive_failures": self.consecutive_failures,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }


def tier_interval(tier: str) -> int:
    """Default scrape interval (seconds) for a currency's tier."""
    settings = get_settings()
    return {
        "major": settings.SCRAPE_INTERVAL_MAJOR,
        "minor": settings.SCRAPE_INTERVAL_STANDARD,
        "exotic": settings.SCRAPE_INTERVAL_EXOTIC,
    }.get(tier, settings.SCRAPE_INTERVAL_EXOTIC)


def get_due_pairs(session: Session, now: datetime) -> list[DuePair]:
    """Return USD→X pairs whose last scrape is older than their interval."""
    from koel.db.models import Currency, ExchangeRateCurrent  # local import avoids cycle

    # Resolve the USD id — every pair uses it as the base.
    usd_id = session.execute(select(Currency.id).where(Currency.code == USD)).scalar_one_or_none()
    if usd_id is None:
        return []

    # Left-join so that currencies without a current row still show up as due.
    stmt = (
        select(
            Currency.code,
            Currency.tier,
            Currency.scrape_interval_seconds,
            ExchangeRateCurrent.observed_at,
        )
        .outerjoin(
            ExchangeRateCurrent,
            and_(
                ExchangeRateCurrent.base_currency_id == usd_id,
                ExchangeRateCurrent.target_currency_id == Currency.id,
            ),
        )
        .where(Currency.is_active.is_(True))
        .where(Currency.code != USD)
    )

    due: list[DuePair] = []
    for code, tier, custom_interval, observed_at in session.execute(stmt):
        interval_s = custom_interval or tier_interval(tier)
        if observed_at is None or (now - observed_at).total_seconds() >= interval_s:
            due.append(DuePair(base_code=USD, target_code=code))
    return due


def get_source_specs(session: Session) -> list[SourceSpec]:
    """All active sources, ready to hand to the scrape service."""
    from koel.db.models import Source

    stmt = select(Source).where(Source.is_active.is_(True))
    rows = session.execute(stmt).scalars().all()
    return [
        SourceSpec(
            id=row.id,
            slug=row.slug,
            base_url=row.base_url,
            weight=row.weight,
            config=row.config or {},
        )
        for row in rows
    ]


def filter_callable_sources(
    session: Session,
    specs: Sequence[SourceSpec],
    now: datetime,
    *,
    cooldown: timedelta = COOLDOWN,
) -> list[SourceSpec]:
    """Consult ``source_health`` + the circuit state machine; persist any
    open→half_open transitions; return only sources we're allowed to call."""
    from koel.db.models import SourceHealth

    if not specs:
        return []

    ids = [s.id for s in specs]
    health = (
        session.execute(select(SourceHealth).where(SourceHealth.source_id.in_(ids))).scalars().all()
    )
    by_id = {h.source_id: h for h in health}

    callable_specs: list[SourceSpec] = []
    for spec in specs:
        row = by_id.get(spec.id)
        state = _state_from_row(row)
        ok, new_state = allow_call(state, now, cooldown=cooldown)
        if new_state is not state and row is not None:
            _apply_state(row, new_state, now)
        if ok:
            callable_specs.append(spec)
    return callable_specs


def get_previous_anchor(
    session: Session,
    base_id: uuid.UUID,
    target_id: uuid.UUID,
) -> Anchor | None:
    """Latest history row for this pair, as an anchor for the delta decision."""
    from koel.db.models import ExchangeRateHistory

    stmt = (
        select(ExchangeRateHistory.rate, ExchangeRateHistory.observed_at)
        .where(ExchangeRateHistory.base_currency_id == base_id)
        .where(ExchangeRateHistory.target_currency_id == target_id)
        .order_by(ExchangeRateHistory.observed_at.desc())
        .limit(1)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    return Anchor(rate=row.rate, observed_at=row.observed_at)


def resolve_currency_ids(
    session: Session,
    codes: Iterable[str],
) -> dict[str, uuid.UUID]:
    from koel.db.models import Currency

    codes = list(codes)
    rows = session.execute(
        select(Currency.code, Currency.id).where(Currency.code.in_(codes))
    ).tuples().all()
    return dict(rows)


def persist_pair_outcome(
    session: Session,
    outcome: PairOutcome,
    *,
    base_id: uuid.UUID,
    target_id: uuid.UUID,
    now: datetime | None = None,
) -> dict[str, object]:
    """Persist everything that resulted from one scrape_pair run.

    Writes (in order): raw observations, current rate UPSERT, history row
    (if should_write_history), per-source health updates. Returns a small
    summary dict for logging/metrics.
    """
    now = now or datetime.now(tz=UTC)
    inserted_observations = _insert_observations(
        session, outcome, base_id=base_id, target_id=target_id
    )

    wrote_history = False
    upserted_current = False
    if outcome.consensus is not None:
        observed_at = _latest_fetched_at(outcome) or now
        _upsert_current(
            session,
            base_id=base_id,
            target_id=target_id,
            rate=outcome.consensus.rate,
            confidence=outcome.consensus.confidence,
            sources_count=outcome.consensus.sources_count,
            observed_at=observed_at,
        )
        upserted_current = True

        anchor = get_previous_anchor(session, base_id, target_id)
        if should_write_history(outcome.consensus.rate, observed_at, anchor):
            _insert_history(
                session,
                base_id=base_id,
                target_id=target_id,
                rate=outcome.consensus.rate,
                confidence=outcome.consensus.confidence,
                sources_count=outcome.consensus.sources_count,
                observed_at=observed_at,
            )
            wrote_history = True

    transitions = _update_source_health(session, outcome, now=now)

    return {
        "observations_inserted": inserted_observations,
        "current_upserted": upserted_current,
        "history_written": wrote_history,
        "transitions": [t.to_dict() for t in transitions],
    }


def _state_from_row(row: Any) -> CircuitState:
    if row is None:
        return CircuitState(status="closed", consecutive_failures=0, opened_at=None)
    return CircuitState(
        status=row.circuit_state,
        consecutive_failures=row.consecutive_failures,
        opened_at=row.circuit_opened_at,
    )


def _apply_state(row: Any, state: CircuitState, now: datetime) -> None:
    row.circuit_state = state.status
    row.consecutive_failures = state.consecutive_failures
    row.circuit_opened_at = state.opened_at
    row.updated_at = now


def _latest_fetched_at(outcome: PairOutcome) -> datetime | None:
    latest: datetime | None = None
    for o in outcome.outcomes:
        if o.reading is None:
            continue
        if latest is None or o.reading.fetched_at > latest:
            latest = o.reading.fetched_at
    return latest


def _insert_observations(
    session: Session,
    outcome: PairOutcome,
    *,
    base_id: uuid.UUID,
    target_id: uuid.UUID,
) -> int:
    from koel.db.models import RateObservation

    rows = []
    for o in outcome.outcomes:
        if o.reading is None:
            continue
        rows.append(
            {
                "source_id": o.source_id,
                "base_currency_id": base_id,
                "target_currency_id": target_id,
                "rate": o.reading.rate,
                "fetched_at": o.reading.fetched_at,
                "latency_ms": o.reading.latency_ms,
            }
        )
    if not rows:
        return 0
    session.execute(pg_insert(RateObservation).values(rows))
    return len(rows)


def _upsert_current(
    session: Session,
    *,
    base_id: uuid.UUID,
    target_id: uuid.UUID,
    rate: Decimal,
    confidence: Decimal | None,
    sources_count: int,
    observed_at: datetime,
) -> None:
    from koel.db.models import ExchangeRateCurrent

    stmt = pg_insert(ExchangeRateCurrent).values(
        base_currency_id=base_id,
        target_currency_id=target_id,
        rate=rate,
        confidence=confidence,
        sources_count=sources_count,
        observed_at=observed_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            ExchangeRateCurrent.base_currency_id,
            ExchangeRateCurrent.target_currency_id,
        ],
        set_={
            "rate": stmt.excluded.rate,
            "confidence": stmt.excluded.confidence,
            "sources_count": stmt.excluded.sources_count,
            "observed_at": stmt.excluded.observed_at,
        },
    )
    session.execute(stmt)


def _insert_history(
    session: Session,
    *,
    base_id: uuid.UUID,
    target_id: uuid.UUID,
    rate: Decimal,
    confidence: Decimal | None,
    sources_count: int,
    observed_at: datetime,
) -> None:
    from koel.db.models import ExchangeRateHistory

    session.execute(
        pg_insert(ExchangeRateHistory).values(
            base_currency_id=base_id,
            target_currency_id=target_id,
            rate=rate,
            confidence=confidence,
            sources_count=sources_count,
            observed_at=observed_at,
        )
    )


def _update_source_health(
    session: Session, outcome: PairOutcome, *, now: datetime
) -> list[HealthTransition]:
    from koel.db.models import Source, SourceHealth

    ids = [o.source_id for o in outcome.outcomes]
    if not ids:
        return []
    rows = (
        session.execute(select(SourceHealth).where(SourceHealth.source_id.in_(ids))).scalars().all()
    )
    by_id = {r.source_id: r for r in rows}
    slugs: dict[uuid.UUID, str] = dict(
        session.execute(select(Source.id, Source.slug).where(Source.id.in_(ids))).tuples().all()
    )

    transitions: list[HealthTransition] = []
    for o in outcome.outcomes:
        row = by_id.get(o.source_id)
        if row is None:
            continue
        old_state = _state_from_row(row)
        if o.success:
            row.last_success_at = now
            latency = o.reading.latency_ms if o.reading else None
            if latency is not None:
                row.avg_latency_ms = _rolling_latency(row.avg_latency_ms, latency)
            new_state = on_success(old_state)
        else:
            row.last_failure_at = now
            row.total_failures = (row.total_failures or 0) + 1
            new_state = on_failure(old_state, now)
        _apply_state(row, new_state, now)
        row.total_requests = (row.total_requests or 0) + 1

        if old_state.status != new_state.status:
            transitions.append(
                HealthTransition(
                    source_id=o.source_id,
                    source_slug=slugs.get(o.source_id, str(o.source_id)),
                    from_status=old_state.status,
                    to_status=new_state.status,
                    consecutive_failures=new_state.consecutive_failures,
                    opened_at=new_state.opened_at,
                )
            )
    return transitions


def _rolling_latency(current: Decimal | None, new_ms: int) -> Decimal:
    """EWMA on latency, alpha=0.2. Cheap and avoids needing a separate table."""
    if current is None:
        return Decimal(new_ms)
    alpha = Decimal("0.2")
    return (current * (Decimal(1) - alpha) + Decimal(new_ms) * alpha).quantize(Decimal("0.01"))


def all_usd_rates(session: Session) -> dict[str, Decimal]:
    """Snapshot of the current USD→X table, for cross-rate materialization."""
    from koel.db.models import Currency, ExchangeRateCurrent

    usd_id = session.execute(select(Currency.id).where(Currency.code == USD)).scalar_one_or_none()
    if usd_id is None:
        return {}

    stmt = (
        select(Currency.code, ExchangeRateCurrent.rate)
        .join(ExchangeRateCurrent, ExchangeRateCurrent.target_currency_id == Currency.id)
        .where(ExchangeRateCurrent.base_currency_id == usd_id)
    )
    return dict(session.execute(stmt).tuples().all())


# Postgres' wire protocol caps at 65_535 parameters per Bind. Each cross-rate
# row carries 6 params, so 10_000 rows per statement stays comfortably under
# the ceiling even as the column list grows. With ~155 currencies in seed,
# the full cross set is ~23_000 rows — batching here is load-bearing.
CROSS_RATE_BATCH_SIZE = 10_000


def _chunks(rows: list[dict[str, object]], size: int) -> Iterator[list[dict[str, object]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def materialize_cross_rates(session: Session, *, now: datetime | None = None) -> int:
    """Derive every non-USD cross rate from the current USD table and UPSERT.

    This is the read-side companion to the USD-pivot scraping strategy:
    scrape only USD→X, compute X→Y = USD→Y / USD→X, and persist so the API
    can answer any pair from a hot index hit.
    """
    from koel.db.models import Currency, ExchangeRateCurrent
    from koel.domain.pivot import derive_all_cross_rates

    now = now or datetime.now(tz=UTC)

    usd_rates = all_usd_rates(session)
    if not usd_rates:
        return 0

    id_by_code = dict(
        session.execute(
            select(Currency.code, Currency.id).where(Currency.is_active.is_(True))
        ).tuples().all()
    )
    codes = [c for c in id_by_code if c in usd_rates or c == USD]
    cross = derive_all_cross_rates(usd_rates, codes=codes)

    # Only write non-USD-base pairs — USD→X is already maintained by the scraper.
    rows: list[dict[str, object]] = [
        {
            "base_currency_id": id_by_code[b],
            "target_currency_id": id_by_code[t],
            "rate": rate,
            "confidence": None,
            "sources_count": 0,
            "observed_at": now,
        }
        for (b, t), rate in cross.items()
        if b != USD and b in id_by_code and t in id_by_code
    ]
    if not rows:
        return 0

    for batch in _chunks(rows, CROSS_RATE_BATCH_SIZE):
        stmt = pg_insert(ExchangeRateCurrent).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ExchangeRateCurrent.base_currency_id,
                ExchangeRateCurrent.target_currency_id,
            ],
            set_={
                "rate": stmt.excluded.rate,
                "observed_at": stmt.excluded.observed_at,
            },
        )
        session.execute(stmt)
    return len(rows)


__all__ = [
    "DuePair",
    "all_usd_rates",
    "filter_callable_sources",
    "get_due_pairs",
    "get_previous_anchor",
    "get_source_specs",
    "materialize_cross_rates",
    "persist_pair_outcome",
    "resolve_currency_ids",
    "tier_interval",
]
