from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from koel.api.deps import get_db, require_admin
from koel.api.schemas import AuditEntryInfo, AuditLogResponse
from koel.db.audit import AuditEntry, list_recent_audit

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _entry_payload(entry: AuditEntry) -> AuditEntryInfo:
    return AuditEntryInfo(
        action=entry.action,
        actor_user_id=str(entry.actor_user_id) if entry.actor_user_id else None,
        subject_type=entry.subject_type,
        subject_id=str(entry.subject_id) if entry.subject_id else None,
        metadata=entry.meta,
        ip_address=entry.ip_address,
        occurred_at=entry.occurred_at,
    )


@router.get("/audit", response_model=AuditLogResponse, summary="Recent audit-log entries")
def get_audit_log(
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    action: Annotated[str | None, Query(description="Filter to one action, e.g. apikey.create")] = None,
) -> AuditLogResponse:
    entries = list_recent_audit(session, limit=limit, action=action)
    return AuditLogResponse(entries=[_entry_payload(e) for e in entries])
