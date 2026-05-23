from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from koel.db.models import AuditLog

# Action names use a dotted ``noun.verb`` scheme so they group cleanly in
# queries (e.g. all ``apikey.*`` events, or everything an actor did).
ACTION_USER_PROMOTE = "user.promote"
ACTION_USER_DEMOTE = "user.demote"
ACTION_APIKEY_GROUP_CREATE = "apikey.group.create"
ACTION_APIKEY_GROUP_DELETE = "apikey.group.delete"
ACTION_APIKEY_CREATE = "apikey.create"
ACTION_APIKEY_REVOKE = "apikey.revoke"


def record_audit(
    session: Session,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Append one audit entry. Does not commit — the caller's transaction does."""
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            meta=meta or {},
            ip_address=ip_address,
        )
    )


@dataclass(frozen=True, slots=True)
class AuditEntry:
    action: str
    actor_user_id: uuid.UUID | None
    subject_type: str | None
    subject_id: uuid.UUID | None
    meta: dict[str, Any]
    ip_address: str | None
    occurred_at: datetime


def list_recent_audit(
    session: Session,
    *,
    limit: int = 50,
    action: str | None = None,
) -> list[AuditEntry]:
    """Most-recent-first audit entries, optionally filtered to one action."""
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(limit)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    rows = session.execute(stmt).scalars().all()
    return [
        AuditEntry(
            action=r.action,
            actor_user_id=r.actor_user_id,
            subject_type=r.subject_type,
            subject_id=r.subject_id,
            meta=r.meta,
            ip_address=str(r.ip_address) if r.ip_address is not None else None,
            occurred_at=r.occurred_at,
        )
        for r in rows
    ]
