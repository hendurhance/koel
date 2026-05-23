from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.types import Date

from koel.db.models import ApiKey, ApiKeyGroup, ApiUsageEvent


@dataclass(frozen=True, slots=True)
class UsageDayRow:
    date: date
    requests: int
    errors: int
    avg_response_time_ms: Decimal | None
    total_bytes: int


@dataclass(frozen=True, slots=True)
class UsageEndpointRow:
    endpoint: str
    requests: int
    errors: int
    avg_response_time_ms: Decimal | None
    total_bytes: int


def _base_select(
    *columns: Any,
    user_id: uuid.UUID,
    start: datetime,
    end: datetime,
    group_id: uuid.UUID | None,
    key_id: uuid.UUID | None,
) -> Select[Any]:
    error_flag = case((ApiUsageEvent.status_code >= 400, 1), else_=0)
    stmt = (
        select(
            *columns,
            func.count().label("requests"),
            func.coalesce(func.sum(error_flag), 0).label("errors"),
            func.avg(ApiUsageEvent.response_time_ms).label("avg_ms"),
            func.coalesce(func.sum(ApiUsageEvent.bytes_sent), 0).label("total_bytes"),
        )
        .join(ApiKey, ApiKey.id == ApiUsageEvent.api_key_id)
        .join(ApiKeyGroup, ApiKeyGroup.id == ApiKey.group_id)
        .where(ApiKeyGroup.user_id == user_id)
        .where(ApiUsageEvent.occurred_at >= start)
        .where(ApiUsageEvent.occurred_at < end)
    )
    if group_id is not None:
        stmt = stmt.where(ApiKey.group_id == group_id)
    if key_id is not None:
        stmt = stmt.where(ApiUsageEvent.api_key_id == key_id)
    return stmt


def summarize_by_day(
    session: Session,
    *,
    user_id: uuid.UUID,
    start: datetime,
    end: datetime,
    group_id: uuid.UUID | None = None,
    key_id: uuid.UUID | None = None,
) -> list[UsageDayRow]:
    day_col = cast(ApiUsageEvent.occurred_at, Date).label("day")
    stmt = (
        _base_select(
            day_col,
            user_id=user_id,
            start=start,
            end=end,
            group_id=group_id,
            key_id=key_id,
        )
        .group_by(day_col)
        .order_by(day_col.asc())
    )
    return [
        UsageDayRow(
            date=row.day,
            requests=row.requests,
            errors=row.errors,
            avg_response_time_ms=row.avg_ms,
            total_bytes=row.total_bytes,
        )
        for row in session.execute(stmt).all()
    ]


def summarize_by_endpoint(
    session: Session,
    *,
    user_id: uuid.UUID,
    start: datetime,
    end: datetime,
    group_id: uuid.UUID | None = None,
    key_id: uuid.UUID | None = None,
) -> list[UsageEndpointRow]:
    stmt = (
        _base_select(
            ApiUsageEvent.endpoint,
            user_id=user_id,
            start=start,
            end=end,
            group_id=group_id,
            key_id=key_id,
        )
        .group_by(ApiUsageEvent.endpoint)
        .order_by(func.count().desc())
    )
    return [
        UsageEndpointRow(
            endpoint=row.endpoint,
            requests=row.requests,
            errors=row.errors,
            avg_response_time_ms=row.avg_ms,
            total_bytes=row.total_bytes,
        )
        for row in session.execute(stmt).all()
    ]


__all__ = [
    "UsageDayRow",
    "UsageEndpointRow",
    "summarize_by_day",
    "summarize_by_endpoint",
]
