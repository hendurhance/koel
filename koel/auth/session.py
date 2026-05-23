from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

SESSION_KEY_PREFIX = "session:"
USER_INDEX_PREFIX = "user_sessions:"


class RedisLike(Protocol):
    """Subset of redis.Redis we depend on. Lets tests use a lightweight fake."""

    def setex(self, name: str, time: int, value: str | bytes) -> object: ...
    def get(self, name: str) -> bytes | str | None: ...
    def delete(self, *names: str) -> int: ...
    def expire(self, name: str, time: int) -> bool: ...
    def sadd(self, name: str, *values: str) -> int: ...
    def srem(self, name: str, *values: str) -> int: ...
    def smembers(self, name: str) -> set[bytes] | set[str]: ...


@dataclass(frozen=True, slots=True)
class SessionData:
    session_id: str
    user_id: uuid.UUID
    created_at: datetime


def _decode(raw: bytes | str | None) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return raw


def _new_session_id() -> str:
    return secrets.token_urlsafe(24)


class SessionStore:
    def __init__(self, redis: RedisLike, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def create(self, user_id: uuid.UUID) -> SessionData:
        session_id = _new_session_id()
        now = datetime.now(tz=UTC)
        payload = json.dumps({"user_id": str(user_id), "created_at": now.isoformat()})
        self._redis.setex(SESSION_KEY_PREFIX + session_id, self._ttl, payload)
        self._redis.sadd(USER_INDEX_PREFIX + str(user_id), session_id)
        self._redis.expire(USER_INDEX_PREFIX + str(user_id), self._ttl)
        return SessionData(session_id=session_id, user_id=user_id, created_at=now)

    def get(self, session_id: str) -> SessionData | None:
        raw = _decode(self._redis.get(SESSION_KEY_PREFIX + session_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return SessionData(
            session_id=session_id,
            user_id=uuid.UUID(data["user_id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def touch(self, session_id: str) -> None:
        """Extend the sliding TTL. Called on every authenticated request."""
        self._redis.expire(SESSION_KEY_PREFIX + session_id, self._ttl)

    def revoke(self, session_id: str) -> None:
        data = self.get(session_id)
        self._redis.delete(SESSION_KEY_PREFIX + session_id)
        if data is not None:
            self._redis.srem(USER_INDEX_PREFIX + str(data.user_id), session_id)

    def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        index_key = USER_INDEX_PREFIX + str(user_id)
        members = self._redis.smembers(index_key)
        ids = [sid for sid in (_decode(m) for m in members) if sid]
        if ids:
            self._redis.delete(*(SESSION_KEY_PREFIX + sid for sid in ids))
        self._redis.delete(index_key)
        return len(ids)
