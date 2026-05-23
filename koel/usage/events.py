from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

STREAM_KEY = "usage:stream:events"
DEFAULT_MAXLEN = 1_000_000


class StreamRedis(Protocol):
    def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int | None = ...,
        approximate: bool = ...,
    ) -> bytes: ...


@dataclass(frozen=True, slots=True)
class UsageEvent:
    api_key_id: uuid.UUID
    endpoint: str
    method: str
    status_code: int
    response_time_ms: int | None
    bytes_sent: int | None
    ip_address: str | None
    occurred_at: datetime


def _encode(event: UsageEvent) -> dict[str, str]:
    return {
        "api_key_id": str(event.api_key_id),
        "endpoint": event.endpoint,
        "method": event.method,
        "status_code": str(event.status_code),
        "response_time_ms": "" if event.response_time_ms is None else str(event.response_time_ms),
        "bytes_sent": "" if event.bytes_sent is None else str(event.bytes_sent),
        "ip_address": event.ip_address or "",
        "occurred_at": event.occurred_at.isoformat(),
    }


class UsageRecorder:
    def __init__(
        self,
        redis: StreamRedis,
        *,
        stream_key: str = STREAM_KEY,
        maxlen: int = DEFAULT_MAXLEN,
    ) -> None:
        self._redis = redis
        self._stream_key = stream_key
        self._maxlen = maxlen

    @property
    def stream_key(self) -> str:
        return self._stream_key

    def record(self, event: UsageEvent) -> None:
        self._redis.xadd(
            self._stream_key,
            _encode(event),
            maxlen=self._maxlen,
            approximate=True,
        )


__all__ = [
    "DEFAULT_MAXLEN",
    "STREAM_KEY",
    "StreamRedis",
    "UsageEvent",
    "UsageRecorder",
]
