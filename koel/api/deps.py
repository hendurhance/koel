from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from redis import Redis
from sqlalchemy.orm import Session

from koel.auth.api_keys import hash_api_key
from koel.auth.rate_limit import RateLimiter
from koel.auth.session import SessionStore
from koel.config import get_settings
from koel.db.api_keys import ApiKeyRow, find_active_key, touch_last_used
from koel.db.auth import UserRow, get_user
from koel.db.session import session_scope

# Redis is generic in the type stubs only; ``Redis[bytes]`` isn't subscriptable
# at runtime (FastAPI would crash resolving the annotation), so alias it.
if TYPE_CHECKING:
    RedisClient = Redis[bytes]
else:
    RedisClient = Redis


def get_db() -> Iterator[Session]:
    with session_scope() as session:
        yield session


@lru_cache(maxsize=1)
def _redis_client() -> RedisClient:
    settings = get_settings()
    return Redis.from_url(settings.REDIS_URL, decode_responses=False)


def get_redis() -> RedisClient:
    return _redis_client()


def get_session_store(redis: Annotated[RedisClient, Depends(get_redis)]) -> SessionStore:
    settings = get_settings()
    return SessionStore(redis, ttl_seconds=settings.SESSION_TTL_SECONDS)


def get_rate_limiter(redis: Annotated[RedisClient, Depends(get_redis)]) -> RateLimiter:
    return RateLimiter(redis)


def get_current_user(
    session: Annotated[Session, Depends(get_db)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    session_cookie: Annotated[str | None, Cookie(alias="koel_session")] = None,
) -> UserRow | None:
    if not session_cookie:
        return None
    data = store.get(session_cookie)
    if data is None:
        return None
    user = get_user(session, data.user_id)
    if user is None:
        store.revoke(session_cookie)
        return None
    store.touch(session_cookie)
    return user


def require_user(user: Annotated[UserRow | None, Depends(get_current_user)]) -> UserRow:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth required")
    return user


def require_admin(user: Annotated[UserRow, Depends(require_user)]) -> UserRow:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


def _maybe_touch_last_used(
    session: Session,
    redis: RedisClient,
    key: ApiKeyRow,
    *,
    now: datetime,
) -> None:
    """Update ``last_used_at`` at most once per ``KEY_TOUCH_THROTTLE_SECONDS``
    per key — avoids hot-path write contention on high-traffic keys."""
    settings = get_settings()
    flag_key = f"key-touched:{key.id}"
    acquired = redis.set(flag_key, b"1", ex=settings.KEY_TOUCH_THROTTLE_SECONDS, nx=True)
    if acquired:
        touch_last_used(session, key_id=key.id, at=now)


def get_current_api_key(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKeyRow | None:
    """Returns ``None`` only when the header is absent. A *present-but-invalid*
    key raises 401 here so callers get a meaningful diagnostic instead of the
    misleading "X-API-Key required" further down the dep chain.
    """
    if x_api_key is None:
        return None
    # Trim copy/paste whitespace; a trailing newline in `curl -H` is the #1
    # cause of "key not found" reports.
    raw = x_api_key.strip()
    if not raw:
        return None
    key = find_active_key(session, key_hash=hash_api_key(raw))
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid, revoked, or expired X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    _maybe_touch_last_used(session, redis, key, now=datetime.now(tz=UTC))
    # Stashed so UsageMiddleware can attribute the request without re-hashing.
    request.state.koel_api_key_id = key.id
    return key


def require_scope_or_session(scope: str) -> Callable[..., UserRow | ApiKeyRow | None]:
    """Factory: dep that accepts *either* a session cookie *or* a valid API
    key with the given scope.

    Session users (dashboard operators) short-circuit past scope and rate-
    limit checks — they already authenticated as themselves, and per-key
    controls exist for programmatic integrations, not humans.

    When ``API_KEYS_REQUIRED=false`` (dev convenience), the whole check
    becomes a no-op — useful for local tinkering before bootstrapping a key.
    """

    def _dep(
        response: Response,
        user: Annotated[UserRow | None, Depends(get_current_user)],
        key: Annotated[ApiKeyRow | None, Depends(get_current_api_key)],
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> UserRow | ApiKeyRow | None:
        if user is not None:
            return user

        settings = get_settings()
        if not settings.API_KEYS_REQUIRED:
            return key
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-API-Key required",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        if scope not in key.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing scope: {scope}",
            )
        result = limiter.check(key.id, key.rate_limit_per_min)
        response.headers["X-RateLimit-Limit"] = str(key.rate_limit_per_min)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(result.retry_after_seconds)},
            )
        return key

    return _dep


# Module-level scope deps — routes reference these so tests can override the
# exact callable via ``app.dependency_overrides``.
require_rates_read = require_scope_or_session("rates:read")
