from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from koel.api.deps import get_db, require_user
from koel.api.schemas import (
    GroupCreateInput,
    GroupInfo,
    GroupsResponse,
    KeyCreatedResponse,
    KeyCreateInput,
    KeyInfo,
    KeysResponse,
)
from koel.auth.api_keys import generate_api_key
from koel.db.api_keys import (
    DEFAULT_SCOPES,
    ApiKeyGroupRow,
    ApiKeyRow,
    create_group,
    create_key,
    delete_group,
    get_group,
    list_groups,
    list_keys,
    revoke_key,
)
from koel.db.audit import (
    ACTION_APIKEY_CREATE,
    ACTION_APIKEY_GROUP_CREATE,
    ACTION_APIKEY_GROUP_DELETE,
    ACTION_APIKEY_REVOKE,
    record_audit,
)
from koel.db.auth import UserRow
from koel.observability.logging import get_logger

router = APIRouter(prefix="/keys", tags=["keys"])
log = get_logger("koel.api.keys")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _group_payload(row: ApiKeyGroupRow) -> GroupInfo:
    return GroupInfo(
        id=str(row.id),
        name=row.name,
        description=row.description,
        created_at=row.created_at,
        keys_count=row.keys_count,
    )


def _key_payload(row: ApiKeyRow) -> KeyInfo:
    return KeyInfo(
        id=str(row.id),
        group_id=str(row.group_id),
        name=row.name,
        key_prefix=row.key_prefix,
        scopes=row.scopes,
        rate_limit_per_min=row.rate_limit_per_min,
        is_active=row.is_active,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


@router.get("/groups", response_model=GroupsResponse, summary="List your key groups")
def list_my_groups(
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> GroupsResponse:
    rows = list_groups(session, user_id=user.id)
    return GroupsResponse(groups=[_group_payload(r) for r in rows])


@router.post(
    "/groups",
    response_model=GroupInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Create a key group",
)
def create_my_group(
    payload: GroupCreateInput,
    request: Request,
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> GroupInfo:
    row = create_group(session, user_id=user.id, name=payload.name, description=payload.description)
    record_audit(
        session,
        action=ACTION_APIKEY_GROUP_CREATE,
        actor_user_id=user.id,
        subject_type="apikey_group",
        subject_id=row.id,
        meta={"name": row.name},
        ip_address=_client_ip(request),
    )
    log.info("keys.group.create", group_id=str(row.id), user_id=str(user.id))
    return _group_payload(row)


@router.get("/groups/{group_id}", response_model=GroupInfo, summary="Get one group")
def get_my_group(
    group_id: uuid.UUID,
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> GroupInfo:
    row = get_group(session, group_id=group_id, user_id=user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    return _group_payload(row)


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a group (cascade to its keys)",
)
def delete_my_group(
    group_id: uuid.UUID,
    request: Request,
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    ok = delete_group(session, group_id=group_id, user_id=user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    record_audit(
        session,
        action=ACTION_APIKEY_GROUP_DELETE,
        actor_user_id=user.id,
        subject_type="apikey_group",
        subject_id=group_id,
        ip_address=_client_ip(request),
    )
    log.info("keys.group.delete", group_id=str(group_id), user_id=str(user.id))


@router.get(
    "/groups/{group_id}/keys",
    response_model=KeysResponse,
    summary="List keys in a group",
)
def list_group_keys(
    group_id: uuid.UUID,
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> KeysResponse:
    group = get_group(session, group_id=group_id, user_id=user.id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    rows = list_keys(session, group_id=group_id, user_id=user.id)
    return KeysResponse(keys=[_key_payload(r) for r in rows])


@router.post(
    "/groups/{group_id}/keys",
    response_model=KeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mint a new key (full value shown once)",
)
def create_group_key(
    group_id: uuid.UUID,
    payload: KeyCreateInput,
    request: Request,
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> KeyCreatedResponse:
    from koel.config import get_settings

    settings = get_settings()
    material = generate_api_key()
    scopes = list(payload.scopes) if payload.scopes else list(DEFAULT_SCOPES)
    rate_limit = (
        payload.rate_limit_per_min
        if payload.rate_limit_per_min is not None
        else settings.DEFAULT_RATE_LIMIT_PER_MIN
    )

    row = create_key(
        session,
        group_id=group_id,
        user_id=user.id,
        name=payload.name,
        key_hash=material.hashed,
        key_prefix=material.prefix,
        scopes=scopes,
        rate_limit_per_min=rate_limit,
        expires_at=payload.expires_at,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")

    record_audit(
        session,
        action=ACTION_APIKEY_CREATE,
        actor_user_id=user.id,
        subject_type="apikey",
        subject_id=row.id,
        meta={"group_id": str(group_id), "prefix": material.prefix, "scopes": scopes},
        ip_address=_client_ip(request),
    )
    log.info(
        "keys.key.create",
        key_id=str(row.id),
        group_id=str(group_id),
        user_id=str(user.id),
        prefix=material.prefix,
    )
    return KeyCreatedResponse(key=material.raw, info=_key_payload(row))


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a key",
)
def revoke_my_key(
    key_id: uuid.UUID,
    request: Request,
    user: Annotated[UserRow, Depends(require_user)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    ok = revoke_key(session, key_id=key_id, user_id=user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="key not found")
    record_audit(
        session,
        action=ACTION_APIKEY_REVOKE,
        actor_user_id=user.id,
        subject_type="apikey",
        subject_id=key_id,
        ip_address=_client_ip(request),
    )
    log.info("keys.key.revoke", key_id=str(key_id), user_id=str(user.id))
