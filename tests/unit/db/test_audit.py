from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from koel.db.audit import AuditEntry, list_recent_audit, record_audit
from koel.db.models import AuditLog


class _AddSession:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)


def test_record_audit_builds_row():
    session = _AddSession()
    actor = uuid.uuid4()
    subject = uuid.uuid4()
    record_audit(
        session,
        action="user.promote",
        actor_user_id=actor,
        subject_type="user",
        subject_id=subject,
        meta={"via": "cli"},
        ip_address="1.2.3.4",
    )
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, AuditLog)
    assert row.action == "user.promote"
    assert row.actor_user_id == actor
    assert row.subject_id == subject
    assert row.meta == {"via": "cli"}
    assert row.ip_address == "1.2.3.4"


def test_record_audit_defaults_meta_to_empty():
    session = _AddSession()
    record_audit(session, action="apikey.revoke")
    assert session.added[0].meta == {}


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _ReadSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.statements: list[Any] = []

    def execute(self, stmt: Any) -> _Scalars:
        self.statements.append(stmt)
        return _Scalars(self._rows)


def test_list_recent_audit_maps_rows():
    row = AuditLog(
        action="apikey.create",
        actor_user_id=uuid.uuid4(),
        subject_type="apikey",
        subject_id=uuid.uuid4(),
        meta={"prefix": "abc"},
        ip_address="10.0.0.1",
    )
    row.occurred_at = datetime(2026, 4, 20, tzinfo=UTC)
    session = _ReadSession([row])

    entries = list_recent_audit(session, limit=10)
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, AuditEntry)
    assert entry.action == "apikey.create"
    assert entry.ip_address == "10.0.0.1"
    assert entry.meta == {"prefix": "abc"}
