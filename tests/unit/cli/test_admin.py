from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from koel.cli import app
from koel.db.audit import AuditEntry
from koel.db.auth import UserRow
from typer.testing import CliRunner


class _FakeSession:
    """Stand-in Session — we patch the repo helpers, not the ORM."""

    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.added: list[Any] = []

    def execute(self, stmt: Any) -> Any:  # pragma: no cover — not reached
        self.executed.append(stmt)
        raise AssertionError("repo helpers should be patched; session.execute must not run")

    def add(self, obj: Any) -> None:
        self.added.append(obj)


@pytest.fixture
def patched_session(monkeypatch: pytest.MonkeyPatch):
    @contextmanager
    def _scope():
        yield _FakeSession()

    monkeypatch.setattr("koel.cli.session_scope" if False else "koel.db.session.session_scope", _scope)
    # `from koel.db.session import session_scope` inside the CLI pulls the
    # name into koel.cli, so we patch both the source and the re-export.
    import koel.cli as cli_module

    # The CLI uses local imports inside each command; monkeypatch the source
    # module so those imports pick up our stub.
    monkeypatch.setattr("koel.db.session.session_scope", _scope)
    del cli_module
    return _scope


def _user(email: str, role: str = "user") -> UserRow:
    return UserRow(id=uuid.uuid4(), email=email, role=role, is_active=True)


class TestPromote:
    def test_promotes_existing_user(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        row = _user("a@b.com", role="user")
        updated = UserRow(id=row.id, email=row.email, role="admin", is_active=True)

        captured: dict[str, Any] = {}

        def fake_find(session, email):
            del session
            captured["find_email"] = email
            return row

        def fake_set_role(session, *, email, role):
            del session
            captured["set_email"] = email
            captured["set_role"] = role
            return updated

        monkeypatch.setattr("koel.db.auth.find_user_by_email", fake_find)
        monkeypatch.setattr("koel.db.auth.set_user_role", fake_set_role)

        result = CliRunner().invoke(app, ["admin", "promote", "A@B.com"])
        assert result.exit_code == 0
        assert "promoted a@b.com" in result.stdout
        assert captured["set_role"] == "admin"
        # Lookup + update both see the normalized (lowercase) email.
        assert captured["find_email"] == "a@b.com"
        assert captured["set_email"] == "a@b.com"

    def test_noop_when_already_admin(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        row = _user("a@b.com", role="admin")
        monkeypatch.setattr("koel.db.auth.find_user_by_email", lambda s, e: row)

        # set_user_role must NOT be called when the role already matches.
        def fail_set_role(*a: object, **kw: object) -> UserRow:
            raise AssertionError("set_user_role should not be called for idempotent promote")

        monkeypatch.setattr("koel.db.auth.set_user_role", fail_set_role)

        result = CliRunner().invoke(app, ["admin", "promote", "a@b.com"])
        assert result.exit_code == 0
        assert "already admin" in result.stdout

    def test_errors_on_unknown_user(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        monkeypatch.setattr("koel.db.auth.find_user_by_email", lambda s, e: None)

        result = CliRunner().invoke(app, ["admin", "promote", "ghost@example.com"])
        assert result.exit_code == 1
        # typer prints to stderr by default when err=True.
        assert "no user with email ghost@example.com" in result.stderr


class TestDemote:
    def test_demotes_existing_admin(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        row = _user("a@b.com", role="admin")
        updated = UserRow(id=row.id, email=row.email, role="user", is_active=True)

        monkeypatch.setattr("koel.db.auth.find_user_by_email", lambda s, e: row)
        monkeypatch.setattr(
            "koel.db.auth.set_user_role", lambda s, *, email, role: updated
        )

        result = CliRunner().invoke(app, ["admin", "demote", "a@b.com"])
        assert result.exit_code == 0
        assert "demoted a@b.com" in result.stdout


class TestList:
    def test_prints_empty_message(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        monkeypatch.setattr("koel.db.auth.list_admins", lambda s: [])

        result = CliRunner().invoke(app, ["admin", "list"])
        assert result.exit_code == 0
        assert "no admins" in result.stdout

    def test_prints_each_admin(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        admins = [_user("a@b.com", "admin"), _user("c@d.com", "admin")]
        monkeypatch.setattr("koel.db.auth.list_admins", lambda s: admins)

        result = CliRunner().invoke(app, ["admin", "list"])
        assert result.exit_code == 0
        assert "a@b.com" in result.stdout
        assert "c@d.com" in result.stdout
        assert "active" in result.stdout


class TestAudit:
    def test_promote_records_audit(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        row = _user("a@b.com", role="user")
        updated = UserRow(id=row.id, email=row.email, role="admin", is_active=True)
        monkeypatch.setattr("koel.db.auth.find_user_by_email", lambda s, e: row)
        monkeypatch.setattr("koel.db.auth.set_user_role", lambda s, *, email, role: updated)

        captured: dict[str, Any] = {}

        def fake_record(session: Any, *, action: str, **kw: Any) -> None:
            del session
            captured["action"] = action
            captured.update(kw)

        monkeypatch.setattr("koel.db.audit.record_audit", fake_record)

        result = CliRunner().invoke(app, ["admin", "promote", "a@b.com"])
        assert result.exit_code == 0
        assert captured["action"] == "user.promote"
        assert captured["subject_type"] == "user"
        assert captured["subject_id"] == updated.id
        assert captured["meta"]["via"] == "cli"

    def test_audit_lists_recent_entries(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        entry = AuditEntry(
            action="user.promote",
            actor_user_id=None,
            subject_type="user",
            subject_id=uuid.uuid4(),
            meta={},
            ip_address=None,
            occurred_at=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
        )
        monkeypatch.setattr("koel.db.audit.list_recent_audit", lambda s, **kw: [entry])

        result = CliRunner().invoke(app, ["admin", "audit"])
        assert result.exit_code == 0
        assert "user.promote" in result.stdout
        assert "system" in result.stdout  # actor_user_id None renders as "system"

    def test_audit_empty(self, patched_session, monkeypatch: pytest.MonkeyPatch):
        del patched_session
        monkeypatch.setattr("koel.db.audit.list_recent_audit", lambda s, **kw: [])

        result = CliRunner().invoke(app, ["admin", "audit"])
        assert result.exit_code == 0
        assert "no audit entries" in result.stdout
