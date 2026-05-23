from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer

Money = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]


class CircuitState(StrEnum):
    """Per-source breaker state. Mirrors the DB check constraint on source_health."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class UserRole(StrEnum):
    """Account role. Mirrors the DB check constraint on users.role."""

    USER = "user"
    ADMIN = "admin"


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class RatePoint(_Base):
    """One row of current rate data for a single target."""

    target: str = Field(..., examples=["EUR"])
    rate: Money = Field(..., examples=["0.8500"])
    confidence: Money | None = Field(None, examples=["1.000"])
    sources_count: int = Field(..., ge=0, examples=[3])
    observed_at: datetime


class BaseRatesResponse(_Base):
    base: str = Field(..., examples=["USD"])
    rates: list[RatePoint]


class SinglePairResponse(_Base):
    base: str
    target: str
    rate: Money
    confidence: Money | None
    sources_count: int
    observed_at: datetime


class HistoryPoint(_Base):
    rate: Money
    confidence: Money | None
    sources_count: int | None
    observed_at: datetime


class HistoryResponse(_Base):
    base: str
    target: str
    points: list[HistoryPoint]


class ConvertResponse(_Base):
    from_: str = Field(..., alias="from", serialization_alias="from")
    to: str
    amount: Money
    rate: Money
    result: Money
    observed_at: datetime


class CurrencyInfo(_Base):
    code: str
    name: str
    symbol: str | None
    decimal_digits: int
    tier: str


class CurrenciesResponse(_Base):
    currencies: list[CurrencyInfo]


class SourceHealthInfo(_Base):
    circuit_state: CircuitState
    consecutive_failures: int
    total_requests: int
    total_failures: int
    avg_latency_ms: Money | None
    last_success_at: datetime | None
    last_failure_at: datetime | None


class SourceInfo(_Base):
    slug: str
    name: str
    weight: Money
    is_active: bool
    health: SourceHealthInfo | None


class SourcesResponse(_Base):
    sources: list[SourceInfo]


class RequestLinkInput(_Base):
    email: EmailStr = Field(..., examples=["you@example.com"])


class RequestLinkResponse(_Base):
    """Returned regardless of whether the email exists — avoids enumerating users."""

    delivered: bool = True


class VerifyResponse(_Base):
    user: UserMe


class UserMe(_Base):
    id: str
    email: str
    role: UserRole
    is_active: bool


class LogoutResponse(_Base):
    revoked: int


VerifyResponse.model_rebuild()


class GroupCreateInput(_Base):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=1024)


class GroupInfo(_Base):
    id: str
    name: str
    description: str | None
    created_at: datetime
    keys_count: int


class GroupsResponse(_Base):
    groups: list[GroupInfo]


class KeyCreateInput(_Base):
    name: str = Field(..., min_length=1, max_length=128)
    scopes: list[str] | None = Field(None, examples=[["rates:read"]])
    rate_limit_per_min: int | None = Field(None, ge=1, le=100_000, examples=[60])
    expires_at: datetime | None = None


class KeyInfo(_Base):
    id: str
    group_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_per_min: int
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class KeyCreatedResponse(_Base):
    """Full key is shown exactly once; callers should copy it immediately."""

    key: str = Field(
        ..., description="The full `koel_...` key — store it now, we won't show it again"
    )
    info: KeyInfo


class KeysResponse(_Base):
    keys: list[KeyInfo]


class UsageDayPoint(_Base):
    date: date
    requests: int
    errors: int
    avg_response_time_ms: Money | None
    total_bytes: int


class UsageEndpointPoint(_Base):
    endpoint: str
    requests: int
    errors: int
    avg_response_time_ms: Money | None
    total_bytes: int


class UsageSummaryResponse(_Base):
    range_start: datetime = Field(..., alias="from", serialization_alias="from")
    range_end: datetime = Field(..., alias="to", serialization_alias="to")
    by_day: list[UsageDayPoint]
    by_endpoint: list[UsageEndpointPoint]


class AuditEntryInfo(_Base):
    action: str = Field(..., examples=["apikey.create"])
    actor_user_id: str | None
    subject_type: str | None
    subject_id: str | None
    metadata: dict[str, Any]
    ip_address: str | None
    occurred_at: datetime


class AuditLogResponse(_Base):
    entries: list[AuditEntryInfo]
