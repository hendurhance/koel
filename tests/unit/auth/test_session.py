from __future__ import annotations

import uuid
from typing import Any

import pytest
from koel.auth.session import SESSION_KEY_PREFIX, USER_INDEX_PREFIX, SessionStore


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.ttl: dict[str, int] = {}

    def setex(self, name: str, time: int, value: Any) -> object:
        if isinstance(value, bytes):
            value = value.decode()
        self.kv[name] = value
        self.ttl[name] = time
        return True

    def get(self, name: str) -> bytes | None:
        v = self.kv.get(name)
        return v.encode() if isinstance(v, str) else v

    def delete(self, *names: str) -> int:
        count = 0
        for n in names:
            if n in self.kv:
                del self.kv[n]
                count += 1
            if n in self.sets:
                del self.sets[n]
                count += 1
            self.ttl.pop(n, None)
        return count

    def expire(self, name: str, time: int) -> bool:
        if name in self.kv or name in self.sets:
            self.ttl[name] = time
            return True
        return False

    def sadd(self, name: str, *values: str) -> int:
        before = len(self.sets.get(name, set()))
        self.sets.setdefault(name, set()).update(values)
        return len(self.sets[name]) - before

    def srem(self, name: str, *values: str) -> int:
        s = self.sets.get(name, set())
        removed = 0
        for v in values:
            if v in s:
                s.remove(v)
                removed += 1
        return removed

    def smembers(self, name: str) -> set[bytes]:
        return {v.encode() for v in self.sets.get(name, set())}


@pytest.fixture
def store() -> tuple[SessionStore, FakeRedis]:
    fake = FakeRedis()
    return SessionStore(fake, ttl_seconds=3600), fake


class TestCreateAndGet:
    def test_roundtrip(self, store):
        s, _ = store
        uid = uuid.uuid4()
        data = s.create(uid)
        got = s.get(data.session_id)
        assert got is not None
        assert got.user_id == uid
        assert got.session_id == data.session_id

    def test_create_sets_ttl_on_session_key(self, store):
        s, fake = store
        data = s.create(uuid.uuid4())
        assert fake.ttl[SESSION_KEY_PREFIX + data.session_id] == 3600

    def test_create_indexes_under_user(self, store):
        s, fake = store
        uid = uuid.uuid4()
        data = s.create(uid)
        assert data.session_id in fake.sets[USER_INDEX_PREFIX + str(uid)]

    def test_get_unknown_returns_none(self, store):
        s, _ = store
        assert s.get("nonexistent") is None


class TestTouchAndRevoke:
    def test_touch_extends_ttl(self, store):
        s, fake = store
        data = s.create(uuid.uuid4())
        fake.ttl[SESSION_KEY_PREFIX + data.session_id] = 10  # simulate elapsed time
        s.touch(data.session_id)
        assert fake.ttl[SESSION_KEY_PREFIX + data.session_id] == 3600

    def test_revoke_removes_session(self, store):
        s, fake = store
        data = s.create(uuid.uuid4())
        s.revoke(data.session_id)
        assert s.get(data.session_id) is None
        assert SESSION_KEY_PREFIX + data.session_id not in fake.kv

    def test_revoke_removes_from_user_index(self, store):
        s, fake = store
        uid = uuid.uuid4()
        data = s.create(uid)
        s.revoke(data.session_id)
        assert data.session_id not in fake.sets.get(USER_INDEX_PREFIX + str(uid), set())


class TestRevokeAllForUser:
    def test_removes_every_session(self, store):
        s, _ = store
        uid = uuid.uuid4()
        sessions = [s.create(uid) for _ in range(3)]
        revoked = s.revoke_all_for_user(uid)
        assert revoked == 3
        for sess in sessions:
            assert s.get(sess.session_id) is None

    def test_no_sessions_returns_zero(self, store):
        s, _ = store
        assert s.revoke_all_for_user(uuid.uuid4()) == 0

    def test_does_not_touch_other_users(self, store):
        s, _ = store
        a_uid, b_uid = uuid.uuid4(), uuid.uuid4()
        s.create(a_uid)
        b_sess = s.create(b_uid)
        s.revoke_all_for_user(a_uid)
        assert s.get(b_sess.session_id) is not None
