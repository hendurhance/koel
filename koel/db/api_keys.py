from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

DEFAULT_SCOPES: tuple[str, ...] = ("rates:read",)


@dataclass(frozen=True, slots=True)
class ApiKeyGroupRow:
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    keys_count: int


@dataclass(frozen=True, slots=True)
class ApiKeyRow:
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_per_min: int
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


def create_group(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    description: str | None,
) -> ApiKeyGroupRow:
    from koel.db.models import ApiKeyGroup

    group = ApiKeyGroup(user_id=user_id, name=name, description=description)
    session.add(group)
    session.flush()
    return ApiKeyGroupRow(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        keys_count=0,
    )


def list_groups(session: Session, *, user_id: uuid.UUID) -> list[ApiKeyGroupRow]:
    from koel.db.models import ApiKey, ApiKeyGroup

    keys_count = (
        select(ApiKey.group_id, func.count(ApiKey.id).label("n"))
        .group_by(ApiKey.group_id)
        .subquery()
    )
    stmt = (
        select(
            ApiKeyGroup.id,
            ApiKeyGroup.user_id,
            ApiKeyGroup.name,
            ApiKeyGroup.description,
            ApiKeyGroup.created_at,
            func.coalesce(keys_count.c.n, 0),
        )
        .outerjoin(keys_count, keys_count.c.group_id == ApiKeyGroup.id)
        .where(ApiKeyGroup.user_id == user_id)
        .order_by(ApiKeyGroup.created_at.desc())
    )
    return [ApiKeyGroupRow(*row) for row in session.execute(stmt).all()]


def get_group(
    session: Session, *, group_id: uuid.UUID, user_id: uuid.UUID
) -> ApiKeyGroupRow | None:
    from koel.db.models import ApiKey, ApiKeyGroup

    group = session.execute(
        select(ApiKeyGroup).where(ApiKeyGroup.id == group_id).where(ApiKeyGroup.user_id == user_id)
    ).scalar_one_or_none()
    if group is None:
        return None
    count = session.execute(
        select(func.count(ApiKey.id)).where(ApiKey.group_id == group.id)
    ).scalar_one()
    return ApiKeyGroupRow(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        keys_count=count,
    )


def delete_group(session: Session, *, group_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    from koel.db.models import ApiKeyGroup

    group = session.execute(
        select(ApiKeyGroup).where(ApiKeyGroup.id == group_id).where(ApiKeyGroup.user_id == user_id)
    ).scalar_one_or_none()
    if group is None:
        return False
    session.delete(group)
    session.flush()
    return True


def _key_to_row(key: object, user_id: uuid.UUID) -> ApiKeyRow:
    from koel.db.models import ApiKey

    assert isinstance(key, ApiKey)
    return ApiKeyRow(
        id=key.id,
        group_id=key.group_id,
        user_id=user_id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=list(key.scopes),
        rate_limit_per_min=key.rate_limit_per_min,
        is_active=key.is_active,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        created_at=key.created_at,
    )


def create_key(
    session: Session,
    *,
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    key_hash: str,
    key_prefix: str,
    scopes: list[str],
    rate_limit_per_min: int,
    expires_at: datetime | None = None,
) -> ApiKeyRow | None:
    """Create a key under a group. Returns None if the group doesn't belong to user."""
    from koel.db.models import ApiKey, ApiKeyGroup

    group = session.execute(
        select(ApiKeyGroup).where(ApiKeyGroup.id == group_id).where(ApiKeyGroup.user_id == user_id)
    ).scalar_one_or_none()
    if group is None:
        return None

    key = ApiKey(
        group_id=group_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=scopes,
        rate_limit_per_min=rate_limit_per_min,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(key)
    session.flush()
    return _key_to_row(key, user_id)


def list_keys(session: Session, *, group_id: uuid.UUID, user_id: uuid.UUID) -> list[ApiKeyRow]:
    from koel.db.models import ApiKey, ApiKeyGroup

    stmt = (
        select(ApiKey)
        .join(ApiKeyGroup, ApiKeyGroup.id == ApiKey.group_id)
        .where(ApiKey.group_id == group_id)
        .where(ApiKeyGroup.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return [_key_to_row(k, user_id) for k in session.execute(stmt).scalars().all()]


def revoke_key(session: Session, *, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    from koel.db.models import ApiKey, ApiKeyGroup

    key = session.execute(
        select(ApiKey)
        .join(ApiKeyGroup, ApiKeyGroup.id == ApiKey.group_id)
        .where(ApiKey.id == key_id)
        .where(ApiKeyGroup.user_id == user_id)
    ).scalar_one_or_none()
    if key is None:
        return False
    if key.revoked_at is not None:
        return True  # idempotent
    key.revoked_at = datetime.now(tz=UTC)
    key.is_active = False
    session.flush()
    return True


def find_active_key(session: Session, *, key_hash: str) -> ApiKeyRow | None:
    """Auth-path lookup. Returns None for revoked, inactive, or expired keys."""
    from koel.db.models import ApiKey, ApiKeyGroup

    row = session.execute(
        select(ApiKey, ApiKeyGroup.user_id)
        .join(ApiKeyGroup, ApiKeyGroup.id == ApiKey.group_id)
        .where(ApiKey.key_hash == key_hash)
    ).first()
    if row is None:
        return None
    key, user_id = row
    if not key.is_active or key.revoked_at is not None:
        return None
    if key.expires_at is not None and key.expires_at <= datetime.now(tz=UTC):
        return None
    return _key_to_row(key, user_id)


def touch_last_used(session: Session, *, key_id: uuid.UUID, at: datetime) -> None:
    from koel.db.models import ApiKey

    session.execute(update(ApiKey).where(ApiKey.id == key_id).values(last_used_at=at))


__all__ = [
    "DEFAULT_SCOPES",
    "ApiKeyGroupRow",
    "ApiKeyRow",
    "create_group",
    "create_key",
    "delete_group",
    "find_active_key",
    "get_group",
    "list_groups",
    "list_keys",
    "revoke_key",
    "touch_last_used",
]
