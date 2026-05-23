from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from koel.api.deps import get_db, require_admin, require_user
from koel.api.main import create_app
from koel.db.audit import AuditEntry
from koel.db.auth import UserRow

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def _admin() -> UserRow:
    return UserRow(id=uuid.uuid4(), email="admin@test.dev", role="admin", is_active=True)


def _entry(action: str = "apikey.create") -> AuditEntry:
    return AuditEntry(
        action=action,
        actor_user_id=uuid.uuid4(),
        subject_type="apikey",
        subject_id=uuid.uuid4(),
        meta={"prefix": "abc"},
        ip_address="1.2.3.4",
        occurred_at=NOW,
    )


@pytest.fixture
def admin_client(monkeypatch: pytest.MonkeyPatch):
    from koel.api.routes import admin as admin_route

    canned: dict[str, Any] = {"entries": [_entry()]}
    monkeypatch.setattr(admin_route, "list_recent_audit", lambda s, **kw: canned["entries"])

    def _get_db():
        yield object()

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_admin] = lambda: _admin()
    return TestClient(app), canned


class TestAuditEndpoint:
    def test_admin_lists_audit(self, admin_client):
        client, _ = admin_client
        r = client.get("/admin/audit")
        assert r.status_code == 200
        body = r.json()
        assert len(body["entries"]) == 1
        entry = body["entries"][0]
        assert entry["action"] == "apikey.create"
        assert entry["metadata"] == {"prefix": "abc"}
        assert entry["ip_address"] == "1.2.3.4"

    def test_passes_filters_through(self, admin_client, monkeypatch: pytest.MonkeyPatch):
        client, _ = admin_client
        from koel.api.routes import admin as admin_route

        captured: dict[str, Any] = {}

        def fake_list(session: Any, **kw: Any) -> list[AuditEntry]:
            del session
            captured.update(kw)
            return []

        monkeypatch.setattr(admin_route, "list_recent_audit", fake_list)
        r = client.get("/admin/audit?limit=10&action=user.promote")
        assert r.status_code == 200
        assert captured["limit"] == 10
        assert captured["action"] == "user.promote"

    def test_limit_out_of_range_rejected(self, admin_client):
        client, _ = admin_client
        assert client.get("/admin/audit?limit=0").status_code == 422
        assert client.get("/admin/audit?limit=999").status_code == 422


class TestAuthorization:
    def test_non_admin_forbidden(self):
        app = create_app()
        # Authenticated but not admin: the real require_admin runs and rejects.
        app.dependency_overrides[require_user] = lambda: UserRow(
            id=uuid.uuid4(), email="u@test.dev", role="user", is_active=True
        )
        with TestClient(app) as c:
            assert c.get("/admin/audit").status_code == 403

    def test_unauthenticated_401(self):
        app = create_app()
        with TestClient(app) as c:
            assert c.get("/admin/audit").status_code == 401
