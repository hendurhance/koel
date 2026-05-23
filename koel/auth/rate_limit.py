from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class IncrRedis(Protocol):
    def incr(self, name: str) -> int: ...
    def expire(self, name: str, time: int) -> bool: ...


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter:
    def __init__(self, redis: IncrRedis) -> None:
        self._redis = redis

    def check(
        self,
        key_id: uuid.UUID,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> RateLimitResult:
        now = now or datetime.now(tz=UTC)
        window = int(now.timestamp()) // 60
        bucket_key = f"ratelimit:key:{key_id}:{window}"
        count = self._redis.incr(bucket_key)
        if count == 1:
            # New window — set TTL a bit beyond the minute boundary so a request
            # landing at :59.999 doesn't race TTL expiry on the next INCR.
            self._redis.expire(bucket_key, 70)
        remaining = max(0, limit - count)
        retry_after = 60 - int(now.timestamp()) % 60 if count > limit else 0
        return RateLimitResult(
            allowed=count <= limit,
            remaining=remaining,
            retry_after_seconds=retry_after,
        )
