from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class UserRow:
    id: uuid.UUID
    email: str
    role: str
    is_active: bool


def _to_row(user: object) -> UserRow:
    from koel.db.models import User

    assert isinstance(user, User)
    return UserRow(id=user.id, email=user.email, role=user.role, is_active=user.is_active)


def get_user(session: Session, user_id: uuid.UUID) -> UserRow | None:
    from koel.db.models import User

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return _to_row(user)


def find_or_create_user(
    session: Session,
    email: str,
    *,
    initial_admin_email: str = "",
) -> UserRow:
    """Lookup the user by email; create if missing.

    If ``initial_admin_email`` matches AND no admin exists yet, the new (or
    existing-but-non-admin) user is promoted. This is the bootstrap hook so
    the operator gets admin on first login without an extra step.
    """
    from koel.db.models import User

    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    should_promote = bool(
        initial_admin_email
        and email.lower() == initial_admin_email.lower()
        and not session.execute(select(exists().where(User.role == "admin"))).scalar()
    )

    if user is None:
        user = User(
            email=email,
            role="admin" if should_promote else "user",
            is_active=True,
        )
        session.add(user)
        session.flush()
    elif should_promote and user.role != "admin":
        user.role = "admin"
        session.flush()

    return _to_row(user)


def insert_magic_link(
    session: Session,
    *,
    email: str,
    token_hash: str,
    expires_at: datetime,
    ip_address: IPv4Address | IPv6Address | None = None,
    user_agent: str | None = None,
) -> None:
    from koel.db.models import MagicLink

    link = MagicLink(
        email=email,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=str(ip_address) if ip_address else None,
        user_agent=user_agent,
    )
    session.add(link)
    session.flush()


def consume_magic_link(
    session: Session,
    *,
    token_hash: str,
    now: datetime,
) -> str | None:
    """Atomically mark a link consumed and return the email it was issued for.

    Returns ``None`` if the token is unknown, expired, or already used. The
    UPDATE ... WHERE guards against double-use under concurrent verify calls.
    """
    from koel.db.models import MagicLink

    stmt = (
        update(MagicLink)
        .where(MagicLink.token_hash == token_hash)
        .where(MagicLink.used_at.is_(None))
        .where(MagicLink.expires_at > now)
        .values(used_at=now)
        .returning(MagicLink.email)
    )
    email = session.execute(stmt).scalar_one_or_none()
    return email


def record_login(session: Session, *, user_id: uuid.UUID, at: datetime) -> None:
    from koel.db.models import User

    session.execute(update(User).where(User.id == user_id).values(last_login_at=at))


def find_user_by_email(session: Session, email: str) -> UserRow | None:
    from koel.db.models import User

    user = session.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()
    return _to_row(user) if user is not None else None


def set_user_role(session: Session, *, email: str, role: str) -> UserRow | None:
    """Set a user's role by email. Returns the updated row, or None if unknown.

    Caller is responsible for validating ``role``; this function doesn't care
    what the literal string is so that the admin/user vocabulary can evolve
    without touching persistence.
    """
    from koel.db.models import User

    stmt = (
        update(User)
        .where(User.email == email.lower())
        .values(role=role)
        .returning(User.id, User.email, User.role, User.is_active)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    return UserRow(id=row.id, email=row.email, role=row.role, is_active=row.is_active)


def list_admins(session: Session) -> list[UserRow]:
    from koel.db.models import User

    rows = session.execute(
        select(User).where(User.role == "admin").order_by(User.email)
    ).scalars()
    return [_to_row(r) for r in rows]


__all__ = [
    "UserRow",
    "consume_magic_link",
    "find_or_create_user",
    "find_user_by_email",
    "get_user",
    "insert_magic_link",
    "list_admins",
    "record_login",
    "set_user_role",
]
