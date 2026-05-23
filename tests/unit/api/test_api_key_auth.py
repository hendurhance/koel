from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from koel.api.deps import get_current_api_key, get_db, get_rate_limiter
from koel.api.main import create_app
from koel.auth.rate_limit import RateLimitResult
from koel.db.api_keys import ApiKeyRow
from koel.db.queries import CurrentRateRow

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def _key(**overrides) -> ApiKeyRow:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "group_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "test",
        "key_prefix": "a1b2c3d4",
        "scopes": ["rates:read"],
        "rate_limit_per_min": 60,
        "is_active": True,
        "last_used_at": None,
        "expires_at": None,
        "revoked_at": None,
        "created_at": NOW,
    }
    defaults.update(overrides)
    return ApiKeyRow(**defaults)


class StubLimiter:
    def __init__(self, result: RateLimitResult) -> None:
        self.result = result

    def check(self, key_id, limit, *, now=None):
        return self.result


@pytest.fixture
def app_with_stub(monkeypatch: pytest.MonkeyPatch):
    canned: dict[str, Any] = {
        "key": None,
        "limit_result": RateLimitResult(allowed=True, remaining=59, retry_after_seconds=0),
        "pair": CurrentRateRow(
            base="USD",
            target="EUR",
            rate=Decimal("0.85"),
            confidence=Decimal("1.000"),
            sources_count=3,
            observed_at=NOW,
        ),
    }

    from koel.api.routes import rates as rates_route

    monkeypatch.setattr(rates_route, "get_current_pair", lambda *a, **kw: canned["pair"])

    def _get_db():
        yield object()

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_api_key] = lambda: canned["key"]
    app.dependency_overrides[get_rate_limiter] = lambda: StubLimiter(canned["limit_result"])
    return TestClient(app), canned


class TestAuthGate:
    def test_missing_key_is_401(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get("/rates/current", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 401
        assert r.headers.get("www-authenticate") == "ApiKey"

    def test_valid_key_is_200(self, app_with_stub):
        client, canned = app_with_stub
        canned["key"] = _key()
        r = client.get("/rates/current", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 200
        assert r.headers["X-RateLimit-Limit"] == "60"
        assert r.headers["X-RateLimit-Remaining"] == "59"

    def test_missing_scope_is_403(self, app_with_stub):
        client, canned = app_with_stub
        canned["key"] = _key(scopes=["other:read"])
        r = client.get("/rates/current", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 403
        assert "rates:read" in r.json()["detail"]

    def test_rate_limited_is_429(self, app_with_stub):
        client, canned = app_with_stub
        canned["key"] = _key()
        canned["limit_result"] = RateLimitResult(allowed=False, remaining=0, retry_after_seconds=15)
        r = client.get("/rates/current", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 429
        assert r.headers.get("retry-after") == "15"


class TestAuthDisabled:
    def test_when_api_keys_not_required_no_key_is_ok(self, app_with_stub, monkeypatch):
        from koel.config import get_settings

        # Flip the setting on the cached singleton so the dep short-circuits.
        s = get_settings()
        monkeypatch.setattr(s, "API_KEYS_REQUIRED", False)
        client, _ = app_with_stub
        r = client.get("/rates/current", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 200
