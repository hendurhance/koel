from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from koel.api.deps import get_db, get_redis
from koel.api.main import create_app
from koel.auth.session import SessionStore
from koel.db.auth import UserRow

from tests.unit.auth.test_session import FakeRedis

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


class FakeRedisWithSet(FakeRedis):
    """Adds the `set(nx=True, ex=...)` surface the request-link cooldown uses."""

    def __init__(self) -> None:
        super().__init__()
        self.set_calls: list[tuple[str, str]] = []

    def set(
        self,
        name: str,
        value: Any,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> object | None:
        self.set_calls.append((name, str(value)))
        if nx and name in self.kv:
            return None
        self.kv[name] = value if isinstance(value, str) else value.decode()
        if ex:
            self.ttl[name] = ex
        return True


@pytest.fixture
def app_with_stub(monkeypatch: pytest.MonkeyPatch):
    canned: dict[str, Any] = {
        "consumed_email": None,
        "user": None,
        "get_user_result": None,
        "delay_calls": [],
    }
    redis = FakeRedisWithSet()

    from koel.api.routes import auth as auth_route

    monkeypatch.setattr(auth_route, "insert_magic_link", lambda *a, **kw: None)
    monkeypatch.setattr(auth_route, "consume_magic_link", lambda *a, **kw: canned["consumed_email"])
    monkeypatch.setattr(auth_route, "find_or_create_user", lambda *a, **kw: canned["user"])
    monkeypatch.setattr(auth_route, "record_login", lambda *a, **kw: None)

    class _StubDelay:
        @staticmethod
        def delay(*args: Any, **kwargs: Any) -> None:
            canned["delay_calls"].append((args, kwargs))

    monkeypatch.setattr(auth_route, "send_magic_link_task", _StubDelay)

    # get_current_user resolves the user via db.auth.get_user, so stub there.
    from koel.api import deps as deps_mod

    monkeypatch.setattr(deps_mod, "get_user", lambda _s, _uid: canned["get_user_result"])

    def _get_db():
        yield object()

    def _get_redis():
        return redis

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = _get_redis
    return TestClient(app), canned, redis


def _make_user(*, role: str = "user") -> UserRow:
    return UserRow(id=uuid.uuid4(), email="u@test.dev", role=role, is_active=True)


class TestRequestLink:
    def test_sends_and_returns_202(self, app_with_stub):
        client, canned, _ = app_with_stub
        r = client.post("/auth/request-link", json={"email": "u@test.dev"})
        assert r.status_code == 202
        assert r.json() == {"delivered": True}
        assert len(canned["delay_calls"]) == 1
        args, _ = canned["delay_calls"][0]
        assert args[0] == "u@test.dev"
        assert "/auth/verify?token=" in args[1]

    def test_throttled_does_not_send_again(self, app_with_stub):
        client, canned, _ = app_with_stub
        client.post("/auth/request-link", json={"email": "u@test.dev"})
        r = client.post("/auth/request-link", json={"email": "u@test.dev"})
        assert r.status_code == 202
        assert r.json() == {"delivered": True}
        # Still only one send — second call hit the cooldown.
        assert len(canned["delay_calls"]) == 1

    def test_normalizes_email_lowercase(self, app_with_stub):
        client, canned, _ = app_with_stub
        client.post("/auth/request-link", json={"email": "U@Test.dev"})
        args, _ = canned["delay_calls"][0]
        assert args[0] == "u@test.dev"

    def test_rejects_non_email(self, app_with_stub):
        client, _, _ = app_with_stub
        r = client.post("/auth/request-link", json={"email": "not-an-email"})
        assert r.status_code == 422


class TestVerify:
    def test_success_sets_cookie_and_returns_user(self, app_with_stub):
        client, canned, _ = app_with_stub
        user = _make_user()
        canned["consumed_email"] = "u@test.dev"
        canned["user"] = user

        r = client.get("/auth/verify", params={"token": "raw-token"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == "u@test.dev"
        assert body["user"]["role"] == "user"
        assert "koel_session" in r.cookies
        assert r.cookies["koel_session"]

    def test_invalid_token_returns_400(self, app_with_stub):
        client, canned, _ = app_with_stub
        canned["consumed_email"] = None
        r = client.get("/auth/verify", params={"token": "bad"})
        assert r.status_code == 400
        assert "koel_session" not in r.cookies


class TestLogout:
    def test_without_cookie_returns_zero(self, app_with_stub):
        client, _, _ = app_with_stub
        r = client.post("/auth/logout")
        assert r.status_code == 200
        assert r.json() == {"revoked": 0}

    def test_with_cookie_revokes_session(self, app_with_stub):
        client, _canned, redis = app_with_stub
        # Seed a real session via SessionStore so logout can find + revoke it.
        store = SessionStore(redis, ttl_seconds=3600)
        user = _make_user()
        sess = store.create(user.id)
        client.cookies.set("koel_session", sess.session_id)
        r = client.post("/auth/logout")
        assert r.status_code == 200
        assert r.json() == {"revoked": 1}
        assert store.get(sess.session_id) is None


class TestMe:
    def test_unauthenticated_is_401(self, app_with_stub):
        client, _, _ = app_with_stub
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_authenticated_returns_user(self, app_with_stub):
        client, canned, redis = app_with_stub
        user = _make_user(role="admin")
        canned["get_user_result"] = user
        store = SessionStore(redis, ttl_seconds=3600)
        sess = store.create(user.id)
        client.cookies.set("koel_session", sess.session_id)

        r = client.get("/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == user.email
        assert body["role"] == "admin"

    def test_stale_session_with_missing_user_401s(self, app_with_stub):
        """Session points at a user that no longer exists (or was disabled).
        Deps should revoke and return 401."""
        client, canned, redis = app_with_stub
        canned["get_user_result"] = None
        store = SessionStore(redis, ttl_seconds=3600)
        sess = store.create(uuid.uuid4())
        client.cookies.set("koel_session", sess.session_id)

        r = client.get("/auth/me")
        assert r.status_code == 401
        # Dangling session should be gone.
        assert store.get(sess.session_id) is None
