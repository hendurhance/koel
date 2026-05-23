from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from koel.backups.orchestrator import BackupOutcome

NOW = datetime(2026, 4, 21, 4, 0, tzinfo=UTC)


class _StubSlackTask:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def delay(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


@pytest.fixture
def settings_defaults(monkeypatch: pytest.MonkeyPatch):
    from koel.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "BACKUP_ENABLED", True)
    monkeypatch.setattr(s, "BACKUP_S3_BUCKET", "backups")
    monkeypatch.setattr(s, "BACKUP_S3_PREFIX", "koel")
    monkeypatch.setattr(s, "BACKUP_S3_REGION", "us-east-1")
    monkeypatch.setattr(s, "AWS_ACCESS_KEY_ID", "AK")
    monkeypatch.setattr(s, "AWS_SECRET_ACCESS_KEY", "SK")


@pytest.fixture
def slack_stubs(monkeypatch: pytest.MonkeyPatch):
    from koel.tasks import notify

    success = _StubSlackTask()
    failure = _StubSlackTask()
    monkeypatch.setattr(notify, "slack_backup_success_task", success)
    monkeypatch.setattr(notify, "slack_backup_failure_task", failure)
    return success, failure


class TestGating:
    def test_skipped_when_backup_disabled(self, monkeypatch: pytest.MonkeyPatch, slack_stubs):
        from koel.config import get_settings

        monkeypatch.setattr(get_settings(), "BACKUP_ENABLED", False)
        from koel.tasks.backup import daily_backup_task

        result = daily_backup_task.run()
        assert result == {"skipped": "disabled"}
        success, failure = slack_stubs
        assert success.payloads == [] and failure.payloads == []

    def test_skipped_when_bucket_empty(self, monkeypatch: pytest.MonkeyPatch, slack_stubs):
        from koel.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "BACKUP_ENABLED", True)
        monkeypatch.setattr(s, "BACKUP_S3_BUCKET", "")
        from koel.tasks.backup import daily_backup_task

        result = daily_backup_task.run()
        assert result == {"skipped": "no_bucket"}
        success, failure = slack_stubs
        assert success.payloads == [] and failure.payloads == []


class TestRunOutcomes:
    def test_success_dispatches_slack_and_returns_outcome(
        self, monkeypatch: pytest.MonkeyPatch, settings_defaults, slack_stubs
    ):
        del settings_defaults
        success, failure = slack_stubs
        outcome = BackupOutcome(
            filename="koel-20260421-040000.dump",
            bucket="backups",
            key="koel/koel-20260421-040000.dump",
            size_bytes=1024,
            dump_duration_seconds=0.2,
            total_duration_seconds=0.5,
            occurred_at=NOW,
        )

        async def fake_run_backup(runner, uploader, *, now, tmp_root=None):
            del runner, uploader, now, tmp_root
            return outcome

        monkeypatch.setattr("koel.tasks.backup.run_backup", fake_run_backup)
        from koel.tasks.backup import daily_backup_task

        result = daily_backup_task.run()
        assert result["filename"] == outcome.filename
        assert len(success.payloads) == 1
        assert success.payloads[0]["key"] == outcome.key
        assert failure.payloads == []

    def test_failure_dispatches_slack_and_reraises(
        self, monkeypatch: pytest.MonkeyPatch, settings_defaults, slack_stubs
    ):
        del settings_defaults
        success, failure = slack_stubs

        async def boom(runner, uploader, *, now, tmp_root=None):
            del runner, uploader, now, tmp_root
            raise RuntimeError("pg_dump: connection refused")

        monkeypatch.setattr("koel.tasks.backup.run_backup", boom)
        from koel.tasks.backup import daily_backup_task

        with pytest.raises(RuntimeError, match="connection refused"):
            daily_backup_task.run()

        assert success.payloads == []
        assert len(failure.payloads) == 1
        assert "connection refused" in failure.payloads[0]["error"]
