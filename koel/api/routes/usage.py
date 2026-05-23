from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from koel.api.deps import get_db, require_user
from koel.api.schemas import (
    UsageDayPoint,
    UsageEndpointPoint,
    UsageSummaryResponse,
)
from koel.db.auth import UserRow
from koel.db.usage import (
    UsageDayRow,
    UsageEndpointRow,
    summarize_by_day,
    summarize_by_endpoint,
)

router = APIRouter(prefix="/usage", tags=["usage"])

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 180


def _default_range() -> tuple[datetime, datetime]:
    now = datetime.now(tz=UTC)
    return now - timedelta(days=DEFAULT_WINDOW_DAYS), now


def _day_payload(row: UsageDayRow) -> UsageDayPoint:
    return UsageDayPoint(
        date=row.date,
        requests=row.requests,
        errors=row.errors,
        avg_response_time_ms=row.avg_response_time_ms,
        total_bytes=row.total_bytes,
    )


def _endpoint_payload(row: UsageEndpointRow) -> UsageEndpointPoint:
    return UsageEndpointPoint(
        endpoint=row.endpoint,
        requests=row.requests,
        errors=row.errors,
        avg_response_time_ms=row.avg_response_time_ms,
        total_bytes=row.total_bytes,
    )


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    response_model_by_alias=True,
    summary="Per-day + per-endpoint usage for the caller",
)
def get_summary(
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
    group_id: Annotated[uuid.UUID | None, Query()] = None,
    key_id: Annotated[uuid.UUID | None, Query()] = None,
    range_start: Annotated[datetime | None, Query(alias="from")] = None,
    range_end: Annotated[datetime | None, Query(alias="to")] = None,
) -> UsageSummaryResponse:
    default_start, default_end = _default_range()
    start = range_start or default_start
    end = range_end or default_end

    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="`to` must be after `from`"
        )
    if end - start > timedelta(days=MAX_WINDOW_DAYS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"window too large — max {MAX_WINDOW_DAYS} days",
        )

    days = summarize_by_day(
        session,
        user_id=user.id,
        start=start,
        end=end,
        group_id=group_id,
        key_id=key_id,
    )
    endpoints = summarize_by_endpoint(
        session,
        user_id=user.id,
        start=start,
        end=end,
        group_id=group_id,
        key_id=key_id,
    )
    return UsageSummaryResponse(
        **{"from": start, "to": end},
        by_day=[_day_payload(r) for r in days],
        by_endpoint=[_endpoint_payload(r) for r in endpoints],
    )
