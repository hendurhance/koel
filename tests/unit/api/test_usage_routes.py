from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from koel.api.deps import get_db, require_user
from koel.api.main import create_app
from koel.db.auth import UserRow
from koel.db.usage import UsageDayRow, UsageEndpointRow


def _user() -> UserRow:
    return UserRow(id=uuid.uuid4(), email="u@test.dev", role="user", is_active=True)


@pytest.fixture
def app_with_stub(monkeypatch: pytest.MonkeyPatch):
    canned: dict[str, Any] = {
        "user": _user(),
        "days": [],
        "endpoints": [],
        "last_kwargs": None,
    }

    from koel.api.routes import usage as usage_route

    def _by_day(session, **kw):
        del session
        canned["last_kwargs"] = kw
        return canned["days"]

    def _by_endpoint(session, **kw):
        del session
        return canned["endpoints"]

    monkeypatch.setattr(usage_route, "summarize_by_day", _by_day)
    monkeypatch.setattr(usage_route, "summarize_by_endpoint", _by_endpoint)

    def _get_db():
        yield object()

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: canned["user"]
    return TestClient(app), canned


class TestSummary:
    def test_empty_returns_zero_length_arrays(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get("/usage/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["by_day"] == []
        assert body["by_endpoint"] == []
        assert "from" in body and "to" in body

    def test_populated_response(self, app_with_stub):
        client, canned = app_with_stub
        canned["days"] = [
            UsageDayRow(
                date=date(2026, 4, 20),
                requests=150,
                errors=3,
                avg_response_time_ms=Decimal("42.75"),
                total_bytes=123456,
            )
        ]
        canned["endpoints"] = [
            UsageEndpointRow(
                endpoint="/rates/{base}",
                requests=120,
                errors=2,
                avg_response_time_ms=Decimal("38.0"),
                total_bytes=100000,
            )
        ]
        r = client.get("/usage/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["by_day"][0] == {
            "date": "2026-04-20",
            "requests": 150,
            "errors": 3,
            "avg_response_time_ms": "42.75",
            "total_bytes": 123456,
        }
        assert body["by_endpoint"][0]["endpoint"] == "/rates/{base}"
        assert body["by_endpoint"][0]["avg_response_time_ms"] == "38.0"

    def test_null_avg_serializes_as_null(self, app_with_stub):
        client, canned = app_with_stub
        canned["days"] = [
            UsageDayRow(
                date=date(2026, 4, 20),
                requests=0,
                errors=0,
                avg_response_time_ms=None,
                total_bytes=0,
            )
        ]
        body = client.get("/usage/summary").json()
        assert body["by_day"][0]["avg_response_time_ms"] is None

    def test_filters_pass_through(self, app_with_stub):
        client, canned = app_with_stub
        gid = uuid.uuid4()
        kid = uuid.uuid4()
        r = client.get(
            "/usage/summary",
            params={
                "group_id": str(gid),
                "key_id": str(kid),
                "from": "2026-04-01T00:00:00+00:00",
                "to": "2026-04-20T00:00:00+00:00",
            },
        )
        assert r.status_code == 200
        kw = canned["last_kwargs"]
        assert kw["group_id"] == gid
        assert kw["key_id"] == kid
        assert kw["start"] == datetime(2026, 4, 1, tzinfo=UTC)
        assert kw["end"] == datetime(2026, 4, 20, tzinfo=UTC)

    def test_inverted_range_is_400(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get(
            "/usage/summary",
            params={
                "from": "2026-04-20T00:00:00+00:00",
                "to": "2026-04-01T00:00:00+00:00",
            },
        )
        assert r.status_code == 400

    def test_window_too_large_is_400(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get(
            "/usage/summary",
            params={
                "from": "2024-01-01T00:00:00+00:00",
                "to": "2026-04-20T00:00:00+00:00",
            },
        )
        assert r.status_code == 400
        assert "max 180" in r.json()["detail"]


class TestUnauthenticated:
    def test_requires_session(self):
        # Hit the real dep chain — no require_user override.
        app = create_app()
        with TestClient(app) as c:
            r = c.get("/usage/summary")
            assert r.status_code == 401
