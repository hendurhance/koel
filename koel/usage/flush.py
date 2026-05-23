from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import insert
from sqlalchemy.orm import Session

from koel.db.models import ApiUsageEvent
from koel.usage.events import STREAM_KEY


class RangeDelRedis(Protocol):
    def xrange(
        self, name: str, min: str = "-", max: str = "+", count: int | None = None
    ) -> list[tuple[bytes, dict[bytes, bytes]]]: ...
    def xdel(self, name: str, *ids: bytes | str) -> int: ...


@dataclass(frozen=True, slots=True)
class FlushResult:
    flushed: int
    from_id: str | None
    to_id: str | None


def _decode_str(value: bytes | str) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _decode_optional_int(value: bytes | str) -> int | None:
    s = _decode_str(value)
    return int(s) if s else None


def _decode_optional_str(value: bytes | str) -> str | None:
    s = _decode_str(value)
    return s or None


def _decode_row(data: dict[bytes, bytes]) -> dict[str, Any]:
    # Redis stream returns {b"key": b"val"} — normalize to python types.
    by_key = {_decode_str(k): v for k, v in data.items()}
    return {
        "api_key_id": uuid.UUID(_decode_str(by_key["api_key_id"])),
        "endpoint": _decode_str(by_key["endpoint"]),
        "method": _decode_str(by_key["method"]),
        "status_code": int(_decode_str(by_key["status_code"])),
        "response_time_ms": _decode_optional_int(by_key["response_time_ms"]),
        "bytes_sent": _decode_optional_int(by_key["bytes_sent"]),
        "ip_address": _decode_optional_str(by_key["ip_address"]),
        "occurred_at": datetime.fromisoformat(_decode_str(by_key["occurred_at"])),
    }


def flush_stream(
    session: Session,
    redis: RangeDelRedis,
    *,
    stream_key: str = STREAM_KEY,
    batch_size: int = 5_000,
) -> FlushResult:
    entries = redis.xrange(stream_key, count=batch_size)
    if not entries:
        return FlushResult(flushed=0, from_id=None, to_id=None)

    rows: list[dict[str, Any]] = []
    ids: list[bytes] = []
    for entry_id, data in entries:
        # Malformed entries are dropped but their id is still XDEL'd below so
        # a broken event doesn't jam the stream forever.
        with contextlib.suppress(KeyError, ValueError):
            rows.append(_decode_row(data))
        ids.append(entry_id)

    if rows:
        session.execute(insert(ApiUsageEvent), rows)
        session.flush()

    redis.xdel(stream_key, *ids)
    return FlushResult(
        flushed=len(rows),
        from_id=_decode_str(ids[0]),
        to_id=_decode_str(ids[-1]),
    )


__all__ = ["FlushResult", "flush_stream"]
