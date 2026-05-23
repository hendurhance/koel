from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, TypedDict
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from koel.api.deps import (
    RedisClient,
    get_db,
    get_redis,
    get_session_store,
    require_user,
)
from koel.api.schemas import (
    LogoutResponse,
    RequestLinkInput,
    RequestLinkResponse,
    UserMe,
    UserRole,
    VerifyResponse,
)
from koel.auth.session import SessionStore
from koel.auth.tokens import generate_token, hash_token
from koel.config import get_settings
from koel.db.auth import (
    UserRow,
    consume_magic_link,
    find_or_create_user,
    insert_magic_link,
    record_login,
)
from koel.observability.logging import get_logger
from koel.tasks.notify import send_magic_link_task

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("koel.api.auth")

REQUEST_LINK_COOLDOWN_SECONDS = 60  # per-email anti-spam window


class _SessionCookie(TypedDict):
    max_age: int
    httponly: bool
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    path: str


def _session_cookie_kwargs(ttl: int, *, production: bool) -> _SessionCookie:
    return {
        "max_age": ttl,
        "httponly": True,
        "secure": production,
        "samesite": "lax",
        "path": "/",
    }


def _build_verify_url(base_url: str, token_raw: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/auth/verify?{urlencode({'token': token_raw})}"


def _user_payload(user: UserRow) -> UserMe:
    return UserMe(
        id=str(user.id),
        email=user.email,
        role=UserRole(user.role),
        is_active=user.is_active,
    )


@router.post(
    "/request-link",
    response_model=RequestLinkResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Email a magic sign-in link",
)
def request_link(
    payload: RequestLinkInput,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> RequestLinkResponse:
    settings = get_settings()
    email = payload.email.lower()

    # Anti-spam: at most one send per email per cooldown window. Returning the
    # same response either way avoids leaking "yes, I just sent one recently".
    cooldown_key = f"auth:link-cooldown:{email}"
    if redis.set(cooldown_key, "1", ex=REQUEST_LINK_COOLDOWN_SECONDS, nx=True) is None:
        log.info("auth.request_link.throttled", email=email)
        return RequestLinkResponse(delivered=True)

    token = generate_token()
    ttl = timedelta(seconds=settings.MAGIC_LINK_TTL_SECONDS)
    expires_at = datetime.now(tz=UTC) + ttl

    insert_magic_link(
        session,
        email=email,
        token_hash=token.hashed,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
    )

    link_url = _build_verify_url(
        settings.FRONTEND_BASE_URL or settings.APP_BASE_URL, token.raw
    )
    send_magic_link_task.delay(
        email,
        link_url,
        settings.MAGIC_LINK_TTL_SECONDS // 60,
    )

    log.info("auth.request_link.sent", email=email, expires_at=expires_at.isoformat())
    return RequestLinkResponse(delivered=True)


@router.get(
    "/verify",
    response_model=VerifyResponse,
    summary="Consume a magic link and start a session",
)
def verify(
    token: str,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> VerifyResponse:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    email = consume_magic_link(session, token_hash=hash_token(token), now=now)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid or expired token",
        )

    user = find_or_create_user(session, email, initial_admin_email=settings.INITIAL_ADMIN_EMAIL)
    record_login(session, user_id=user.id, at=now)

    sess = store.create(user.id)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=sess.session_id,
        **_session_cookie_kwargs(settings.SESSION_TTL_SECONDS, production=settings.is_production),
    )

    log.info("auth.verify.ok", user_id=str(user.id), email=user.email)
    return VerifyResponse(user=_user_payload(user))


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="End the current session",
)
def logout(
    response: Response,
    store: Annotated[SessionStore, Depends(get_session_store)],
    session_cookie: Annotated[str | None, Cookie(alias="koel_session")] = None,
) -> LogoutResponse:
    settings = get_settings()
    revoked = 0
    if session_cookie:
        store.revoke(session_cookie)
        revoked = 1
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return LogoutResponse(revoked=revoked)


@router.get("/me", response_model=UserMe, summary="Current authenticated user")
def me(user: Annotated[UserRow, Depends(require_user)]) -> UserMe:
    return _user_payload(user)
