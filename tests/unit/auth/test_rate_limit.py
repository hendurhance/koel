from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from koel.auth.rate_limit import RateLimiter


class FakeIncrRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def incr(self, name: str) -> int:
        self.counters[name] = self.counters.get(name, 0) + 1
        return self.counters[name]

    def expire(self, name: str, time: int) -> bool:
        self.ttls[name] = time
        return True


@pytest.fixture
def limiter() -> tuple[RateLimiter, FakeIncrRedis]:
    redis = FakeIncrRedis()
    return RateLimiter(redis), redis


class TestCheck:
    def test_allows_under_limit(self, limiter):
        lim, _ = limiter
        kid = uuid.uuid4()
        r = lim.check(kid, limit=3)
        assert r.allowed is True
        assert r.remaining == 2
        assert r.retry_after_seconds == 0

    def test_blocks_at_limit_plus_one(self, limiter):
        lim, _ = limiter
        kid = uuid.uuid4()
        now = datetime(2026, 4, 20, 12, 0, 30, tzinfo=UTC)
        for _ in range(3):
            lim.check(kid, limit=3, now=now)
        r = lim.check(kid, limit=3, now=now)
        assert r.allowed is False
        assert r.remaining == 0
        assert r.retry_after_seconds == 30  # 60 - 30

    def test_ttl_set_on_first_hit(self, limiter):
        lim, redis = limiter
        kid = uuid.uuid4()
        lim.check(kid, limit=1)
        # Exactly one TTL key set
        assert len(redis.ttls) == 1
        assert next(iter(redis.ttls.values())) == 70

    def test_new_window_new_bucket(self, limiter):
        lim, redis = limiter
        kid = uuid.uuid4()
        now_a = datetime(2026, 4, 20, 12, 0, 30, tzinfo=UTC)
        now_b = datetime(2026, 4, 20, 12, 1, 30, tzinfo=UTC)
        lim.check(kid, limit=1, now=now_a)
        lim.check(kid, limit=1, now=now_a)
        r = lim.check(kid, limit=1, now=now_b)
        assert r.allowed is True
        assert len(redis.counters) == 2  # one per minute bucket

    def test_isolated_per_key(self, limiter):
        lim, _ = limiter
        a, b = uuid.uuid4(), uuid.uuid4()
        lim.check(a, limit=1)
        lim.check(a, limit=1)
        r = lim.check(b, limit=1)
        assert r.allowed is True
