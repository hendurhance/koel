from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from koel.api.deps import get_db, require_rates_read
from koel.api.schemas import (
    BaseRatesResponse,
    ConvertResponse,
    HistoryPoint,
    HistoryResponse,
    RatePoint,
    SinglePairResponse,
)
from koel.db.queries import (
    get_current_for_base,
    get_current_pair,
    get_history,
    known_currency_codes,
)

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/rates",
    tags=["rates"],
    dependencies=[Depends(require_rates_read)],
)

MAX_HISTORY_LIMIT = 10_000
DEFAULT_HISTORY_WINDOW = timedelta(hours=24)


@router.get(
    "/current",
    response_model=BaseRatesResponse | SinglePairResponse,
    summary="Current rates",
)
def current_rates(
    session: DbSession,
    base: Annotated[str, Query(min_length=3, max_length=3, description="ISO 4217 base code")],
    target: Annotated[
        str | None,
        Query(min_length=3, max_length=3, description="If set, return just this pair"),
    ] = None,
    targets: Annotated[
        list[str] | None,
        Query(description="Optional subset of targets to return (ignored when `target` set)"),
    ] = None,
) -> BaseRatesResponse | SinglePairResponse:
    base = base.upper()

    if target is not None:
        target = target.upper()
        row = get_current_pair(session, base, target)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no current rate for {base}->{target}",
            )
        return SinglePairResponse(
            base=row.base,
            target=row.target,
            rate=row.rate,
            confidence=row.confidence,
            sources_count=row.sources_count,
            observed_at=row.observed_at,
        )

    upper_targets = [t.upper() for t in targets] if targets else None
    rows = get_current_for_base(session, base, targets=upper_targets)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no current rates for base {base}",
        )
    return BaseRatesResponse(
        base=base,
        rates=[
            RatePoint(
                target=r.target,
                rate=r.rate,
                confidence=r.confidence,
                sources_count=r.sources_count,
                observed_at=r.observed_at,
            )
            for r in rows
        ],
    )


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Historical rates for one pair",
)
def history(
    session: DbSession,
    base: Annotated[str, Query(min_length=3, max_length=3)],
    target: Annotated[str, Query(min_length=3, max_length=3)],
    since: Annotated[datetime | None, Query(description="ISO-8601 start (inclusive)")] = None,
    until: Annotated[datetime | None, Query(description="ISO-8601 end (inclusive)")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_HISTORY_LIMIT)] = 500,
) -> HistoryResponse:
    base = base.upper()
    target = target.upper()

    # Default window: last 24h if the caller asked for nothing.
    if since is None and until is None:
        since = datetime.now(tz=UTC) - DEFAULT_HISTORY_WINDOW

    rows = get_history(session, base, target, since=since, until=until, limit=limit)
    return HistoryResponse(
        base=base,
        target=target,
        points=[
            HistoryPoint(
                rate=r.rate,
                confidence=r.confidence,
                sources_count=r.sources_count,
                observed_at=r.observed_at,
            )
            for r in rows
        ],
    )


@router.get(
    "/convert",
    response_model=ConvertResponse,
    summary="Convert an amount between two currencies using the current rate",
)
def convert(
    session: DbSession,
    from_: Annotated[str, Query(alias="from", min_length=3, max_length=3)],
    to: Annotated[str, Query(min_length=3, max_length=3)],
    amount: Annotated[Decimal, Query(gt=0)],
) -> ConvertResponse:
    src = from_.upper()
    dst = to.upper()
    row = get_current_pair(session, src, dst)
    if row is None:
        known = known_currency_codes(session, [src, dst])
        missing = [c for c in (src, dst) if c not in known]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown currency: {', '.join(missing)}",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no current rate for {src}->{dst}",
        )
    return ConvertResponse(
        from_=src,
        to=dst,
        amount=amount,
        rate=row.rate,
        result=(amount * row.rate),
        observed_at=row.observed_at,
    )
