from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from koel.api.deps import get_db, require_user
from koel.api.main import create_app
from koel.db.api_keys import ApiKeyGroupRow, ApiKeyRow
from koel.db.auth import UserRow

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def _user() -> UserRow:
    return UserRow(id=uuid.uuid4(), email="u@test.dev", role="user", is_active=True)


def _group(user_id: uuid.UUID, **overrides) -> ApiKeyGroupRow:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "name": "Default",
        "description": None,
        "created_at": NOW,
        "keys_count": 0,
    }
    defaults.update(overrides)
    return ApiKeyGroupRow(**defaults)


def _key(group_id: uuid.UUID, user_id: uuid.UUID, **overrides) -> ApiKeyRow:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "group_id": group_id,
        "user_id": user_id,
        "name": "primary",
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


@pytest.fixture
def app_with_stub(monkeypatch: pytest.MonkeyPatch):
    user = _user()
    canned: dict[str, Any] = {
        "user": user,
        "groups": [],
        "group": None,
        "keys": [],
        "created_group": None,
        "created_key": None,
        "delete_group_ok": True,
        "revoke_key_ok": True,
    }

    from koel.api.routes import keys as keys_route

    monkeypatch.setattr(keys_route, "list_groups", lambda *a, **kw: canned["groups"])
    monkeypatch.setattr(keys_route, "get_group", lambda *a, **kw: canned["group"])
    monkeypatch.setattr(keys_route, "create_group", lambda *a, **kw: canned["created_group"])
    monkeypatch.setattr(keys_route, "delete_group", lambda *a, **kw: canned["delete_group_ok"])
    monkeypatch.setattr(keys_route, "list_keys", lambda *a, **kw: canned["keys"])
    monkeypatch.setattr(keys_route, "create_key", lambda *a, **kw: canned["created_key"])
    monkeypatch.setattr(keys_route, "revoke_key", lambda *a, **kw: canned["revoke_key_ok"])

    audit: list[dict[str, Any]] = []
    canned["audit"] = audit
    monkeypatch.setattr(keys_route, "record_audit", lambda session, **kw: audit.append(kw))

    def _get_db():
        yield object()

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: canned["user"]
    return TestClient(app), canned


class TestGroups:
    def test_list_empty(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get("/keys/groups")
        assert r.status_code == 200
        assert r.json() == {"groups": []}

    def test_list_returns_groups(self, app_with_stub):
        client, canned = app_with_stub
        canned["groups"] = [_group(canned["user"].id, name="Prod", keys_count=3)]
        r = client.get("/keys/groups")
        body = r.json()
        assert len(body["groups"]) == 1
        assert body["groups"][0]["name"] == "Prod"
        assert body["groups"][0]["keys_count"] == 3

    def test_create_group(self, app_with_stub):
        client, canned = app_with_stub
        uid = canned["user"].id
        canned["created_group"] = _group(uid, name="Prod", description="my prod keys")
        r = client.post("/keys/groups", json={"name": "Prod", "description": "my prod keys"})
        assert r.status_code == 201
        assert r.json()["name"] == "Prod"
        assert r.json()["description"] == "my prod keys"

    def test_get_group_404(self, app_with_stub):
        client, canned = app_with_stub
        canned["group"] = None
        r = client.get(f"/keys/groups/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_get_group_ok(self, app_with_stub):
        client, canned = app_with_stub
        uid = canned["user"].id
        g = _group(uid, name="Prod", keys_count=2)
        canned["group"] = g
        r = client.get(f"/keys/groups/{g.id}")
        assert r.status_code == 200
        assert r.json()["keys_count"] == 2

    def test_delete_group_204(self, app_with_stub):
        client, _ = app_with_stub
        r = client.delete(f"/keys/groups/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_delete_group_404(self, app_with_stub):
        client, canned = app_with_stub
        canned["delete_group_ok"] = False
        r = client.delete(f"/keys/groups/{uuid.uuid4()}")
        assert r.status_code == 404


class TestKeys:
    def test_list_keys_404_when_group_missing(self, app_with_stub):
        client, canned = app_with_stub
        canned["group"] = None
        r = client.get(f"/keys/groups/{uuid.uuid4()}/keys")
        assert r.status_code == 404

    def test_list_keys_ok(self, app_with_stub):
        client, canned = app_with_stub
        uid = canned["user"].id
        g = _group(uid)
        canned["group"] = g
        canned["keys"] = [_key(g.id, uid)]
        r = client.get(f"/keys/groups/{g.id}/keys")
        assert r.status_code == 200
        body = r.json()
        assert len(body["keys"]) == 1
        assert body["keys"][0]["key_prefix"] == "a1b2c3d4"
        # No secret leakage.
        assert "key_hash" not in body["keys"][0]

    def test_create_key_returns_full_value_once(self, app_with_stub):
        client, canned = app_with_stub
        uid = canned["user"].id
        g = _group(uid)
        canned["created_key"] = _key(g.id, uid, name="primary")
        r = client.post(
            f"/keys/groups/{g.id}/keys",
            json={"name": "primary"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["key"].startswith("koel_")
        assert body["info"]["name"] == "primary"
        assert body["info"]["rate_limit_per_min"] == 60
        assert body["info"]["scopes"] == ["rates:read"]

    def test_create_key_group_not_found(self, app_with_stub):
        client, canned = app_with_stub
        canned["created_key"] = None
        r = client.post(
            f"/keys/groups/{uuid.uuid4()}/keys",
            json={"name": "primary"},
        )
        assert r.status_code == 404

    def test_revoke_key_204(self, app_with_stub):
        client, _ = app_with_stub
        r = client.delete(f"/keys/keys/{uuid.uuid4()}")
        assert r.status_code == 204

    def test_revoke_key_404(self, app_with_stub):
        client, canned = app_with_stub
        canned["revoke_key_ok"] = False
        r = client.delete(f"/keys/keys/{uuid.uuid4()}")
        assert r.status_code == 404


class TestAudit:
    def test_create_group_audits(self, app_with_stub):
        client, canned = app_with_stub
        uid = canned["user"].id
        canned["created_group"] = _group(uid, name="Prod")
        client.post("/keys/groups", json={"name": "Prod"})
        assert len(canned["audit"]) == 1
        entry = canned["audit"][0]
        assert entry["action"] == "apikey.group.create"
        assert entry["actor_user_id"] == uid
        assert entry["subject_type"] == "apikey_group"

    def test_create_key_audits(self, app_with_stub):
        client, canned = app_with_stub
        uid = canned["user"].id
        g = _group(uid)
        canned["created_key"] = _key(g.id, uid, name="primary")
        client.post(f"/keys/groups/{g.id}/keys", json={"name": "primary"})
        entry = canned["audit"][-1]
        assert entry["action"] == "apikey.create"
        assert entry["subject_id"] == canned["created_key"].id
        assert entry["meta"]["scopes"] == ["rates:read"]

    def test_revoke_key_audits(self, app_with_stub):
        client, canned = app_with_stub
        client.delete(f"/keys/keys/{uuid.uuid4()}")
        assert canned["audit"][-1]["action"] == "apikey.revoke"

    def test_delete_group_audits(self, app_with_stub):
        client, canned = app_with_stub
        client.delete(f"/keys/groups/{uuid.uuid4()}")
        assert canned["audit"][-1]["action"] == "apikey.group.delete"

    def test_failed_action_does_not_audit(self, app_with_stub):
        client, canned = app_with_stub
        canned["revoke_key_ok"] = False
        r = client.delete(f"/keys/keys/{uuid.uuid4()}")
        assert r.status_code == 404
        assert canned["audit"] == []


class TestUnauthenticated:
    def test_list_groups_401(self, monkeypatch: pytest.MonkeyPatch):
        # No override of require_user — hit it through the real dep chain.
        app = create_app()
        with TestClient(app) as c:
            r = c.get("/keys/groups")
            assert r.status_code == 401
