from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class CurrentRateRow:
    base: str
    target: str
    rate: Decimal
    confidence: Decimal | None
    sources_count: int
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryRow:
    rate: Decimal
    confidence: Decimal | None
    sources_count: int | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class CurrencyRow:
    code: str
    name: str
    symbol: str | None
    decimal_digits: int
    tier: str


@dataclass(frozen=True, slots=True)
class SourceRow:
    slug: str
    name: str
    weight: Decimal
    is_active: bool
    circuit_state: str | None
    consecutive_failures: int | None
    total_requests: int | None
    total_failures: int | None
    avg_latency_ms: Decimal | None
    last_success_at: datetime | None
    last_failure_at: datetime | None


def _resolve_id(session: Session, code: str) -> uuid.UUID | None:
    from koel.db.models import Currency

    return session.execute(select(Currency.id).where(Currency.code == code)).scalar_one_or_none()


def get_current_pair(session: Session, base: str, target: str) -> CurrentRateRow | None:
    """Latest rate for one (base, target) pair."""
    from koel.db.models import Currency, ExchangeRateCurrent

    base_cur = Currency.__table__.alias("base_cur")
    tgt_cur = Currency.__table__.alias("tgt_cur")

    stmt = (
        select(
            base_cur.c.code,
            tgt_cur.c.code,
            ExchangeRateCurrent.rate,
            ExchangeRateCurrent.confidence,
            ExchangeRateCurrent.sources_count,
            ExchangeRateCurrent.observed_at,
        )
        .join(base_cur, base_cur.c.id == ExchangeRateCurrent.base_currency_id)
        .join(tgt_cur, tgt_cur.c.id == ExchangeRateCurrent.target_currency_id)
        .where(base_cur.c.code == base)
        .where(tgt_cur.c.code == target)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    return CurrentRateRow(*row)


def get_current_for_base(
    session: Session,
    base: str,
    *,
    targets: Sequence[str] | None = None,
) -> list[CurrentRateRow]:
    """All current rates for one base, optionally filtered to specific targets."""
    from koel.db.models import Currency, ExchangeRateCurrent

    base_cur = Currency.__table__.alias("base_cur")
    tgt_cur = Currency.__table__.alias("tgt_cur")

    stmt = (
        select(
            base_cur.c.code,
            tgt_cur.c.code,
            ExchangeRateCurrent.rate,
            ExchangeRateCurrent.confidence,
            ExchangeRateCurrent.sources_count,
            ExchangeRateCurrent.observed_at,
        )
        .join(base_cur, base_cur.c.id == ExchangeRateCurrent.base_currency_id)
        .join(tgt_cur, tgt_cur.c.id == ExchangeRateCurrent.target_currency_id)
        .where(base_cur.c.code == base)
        .order_by(tgt_cur.c.code)
    )
    if targets:
        stmt = stmt.where(tgt_cur.c.code.in_(list(targets)))
    return [CurrentRateRow(*row) for row in session.execute(stmt).all()]


def get_history(
    session: Session,
    base: str,
    target: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 500,
) -> list[HistoryRow]:
    """Time series of history rows for a pair, newest first."""
    from koel.db.models import ExchangeRateHistory

    base_id = _resolve_id(session, base)
    target_id = _resolve_id(session, target)
    if base_id is None or target_id is None:
        return []

    stmt = (
        select(
            ExchangeRateHistory.rate,
            ExchangeRateHistory.confidence,
            ExchangeRateHistory.sources_count,
            ExchangeRateHistory.observed_at,
        )
        .where(ExchangeRateHistory.base_currency_id == base_id)
        .where(ExchangeRateHistory.target_currency_id == target_id)
        .order_by(ExchangeRateHistory.observed_at.desc())
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(ExchangeRateHistory.observed_at >= since)
    if until is not None:
        stmt = stmt.where(ExchangeRateHistory.observed_at <= until)
    return [HistoryRow(*row) for row in session.execute(stmt).all()]


def list_active_currencies(session: Session) -> list[CurrencyRow]:
    from koel.db.models import Currency

    stmt = (
        select(
            Currency.code,
            Currency.name,
            Currency.symbol,
            Currency.decimal_digits,
            Currency.tier,
        )
        .where(Currency.is_active.is_(True))
        .order_by(Currency.code)
    )
    return [CurrencyRow(*row) for row in session.execute(stmt).all()]


def list_sources_with_health(session: Session) -> list[SourceRow]:
    from koel.db.models import Source, SourceHealth

    stmt = (
        select(
            Source.slug,
            Source.name,
            Source.weight,
            Source.is_active,
            SourceHealth.circuit_state,
            SourceHealth.consecutive_failures,
            SourceHealth.total_requests,
            SourceHealth.total_failures,
            SourceHealth.avg_latency_ms,
            SourceHealth.last_success_at,
            SourceHealth.last_failure_at,
        )
        .outerjoin(SourceHealth, SourceHealth.source_id == Source.id)
        .order_by(Source.slug)
    )
    return [SourceRow(*row) for row in session.execute(stmt).all()]


def known_currency_codes(session: Session, codes: Iterable[str]) -> set[str]:
    """Return the subset of `codes` that exist as active currencies."""
    from koel.db.models import Currency

    codes = list(codes)
    if not codes:
        return set()
    stmt = select(Currency.code).where(Currency.code.in_(codes)).where(Currency.is_active.is_(True))
    return {row[0] for row in session.execute(stmt).all()}


__all__ = [
    "CurrencyRow",
    "CurrentRateRow",
    "HistoryRow",
    "SourceRow",
    "get_current_for_base",
    "get_current_pair",
    "get_history",
    "known_currency_codes",
    "list_active_currencies",
    "list_sources_with_health",
]
