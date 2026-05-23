from __future__ import annotations

from typing import Any

import pytest
from koel.notifications.slack import SlackClient, SlackMessage


class FakeSlackClient(SlackClient):
    def __init__(self, configured: bool = True) -> None:
        super().__init__(webhook_url="https://hooks.slack.com/x" if configured else "")
        self.sent: list[SlackMessage] = []

    def send(self, message: SlackMessage) -> bool:
        self.sent.append(message)
        return True


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch):
    client = FakeSlackClient(configured=True)
    monkeypatch.setattr("koel.tasks.notify.slack_client_from_settings", lambda: client)
    return client


class TestCircuitTask:
    def test_open_transition_sends_alert(self, fake_client):
        from koel.tasks.notify import slack_circuit_transition_task

        payload: dict[str, Any] = {
            "source_slug": "xrates",
            "from_status": "closed",
            "to_status": "open",
            "consecutive_failures": 5,
            "opened_at": "2026-04-20T12:00:00+00:00",
        }
        ok = slack_circuit_transition_task.run(payload)
        assert ok is True
        assert len(fake_client.sent) == 1
        assert "xrates" in fake_client.sent[0].text

    def test_recovery_transition_sends_alert(self, fake_client):
        from koel.tasks.notify import slack_circuit_transition_task

        payload = {
            "source_slug": "xrates",
            "from_status": "half_open",
            "to_status": "closed",
            "consecutive_failures": 0,
            "opened_at": None,
        }
        ok = slack_circuit_transition_task.run(payload)
        assert ok is True
        assert "recovered" in fake_client.sent[0].text

    def test_probe_transition_is_dropped(self, fake_client):
        # closed -> half_open shouldn't fire; it's a probe, not a real event.
        from koel.tasks.notify import slack_circuit_transition_task

        payload = {
            "source_slug": "xrates",
            "from_status": "open",
            "to_status": "half_open",
            "consecutive_failures": 5,
            "opened_at": "2026-04-20T12:00:00+00:00",
        }
        ok = slack_circuit_transition_task.run(payload)
        assert ok is False
        assert fake_client.sent == []

    def test_unconfigured_client_skips(self, monkeypatch: pytest.MonkeyPatch):
        unset = FakeSlackClient(configured=False)
        monkeypatch.setattr("koel.tasks.notify.slack_client_from_settings", lambda: unset)
        from koel.tasks.notify import slack_circuit_transition_task

        ok = slack_circuit_transition_task.run(
            {
                "source_slug": "xrates",
                "from_status": "closed",
                "to_status": "open",
                "consecutive_failures": 5,
                "opened_at": None,
            }
        )
        assert ok is False
        assert unset.sent == []


class TestCrawlCompleteTask:
    def test_dispatch_sends_summary(self, fake_client):
        from koel.tasks.notify import slack_crawl_complete_task

        payload = {
            "enqueued": 10,
            "scraped": 10,
            "had_consensus": 8,
            "circuit_transitions": 1,
            "duration_seconds": 2.5,
            "occurred_at": "2026-04-20T12:00:00+00:00",
        }
        ok = slack_crawl_complete_task.run(payload)
        assert ok is True
        assert "10/10" in fake_client.sent[0].text

    def test_unconfigured_is_noop(self, monkeypatch: pytest.MonkeyPatch):
        unset = FakeSlackClient(configured=False)
        monkeypatch.setattr("koel.tasks.notify.slack_client_from_settings", lambda: unset)
        from koel.tasks.notify import slack_crawl_complete_task

        payload = {
            "enqueued": 10,
            "scraped": 10,
            "had_consensus": 8,
            "circuit_transitions": 0,
            "duration_seconds": 2.5,
            "occurred_at": "2026-04-20T12:00:00+00:00",
        }
        ok = slack_crawl_complete_task.run(payload)
        assert ok is False


class TestBackupSuccessTask:
    def test_sends_message_with_filename(self, fake_client):
        from koel.tasks.notify import slack_backup_success_task

        payload: dict[str, Any] = {
            "filename": "koel-20260421-040000.dump",
            "bucket": "b",
            "key": "koel/koel-20260421-040000.dump",
            "size_bytes": 1024 * 1024,
            "dump_duration_seconds": 0.5,
            "total_duration_seconds": 1.0,
            "occurred_at": "2026-04-21T04:00:00+00:00",
        }
        ok = slack_backup_success_task.run(payload)
        assert ok is True
        assert "koel-20260421-040000.dump" in fake_client.sent[0].text

    def test_unconfigured_is_noop(self, monkeypatch: pytest.MonkeyPatch):
        unset = FakeSlackClient(configured=False)
        monkeypatch.setattr("koel.tasks.notify.slack_client_from_settings", lambda: unset)
        from koel.tasks.notify import slack_backup_success_task

        ok = slack_backup_success_task.run(
            {
                "filename": "x.dump",
                "bucket": "b",
                "key": "k",
                "size_bytes": 0,
                "dump_duration_seconds": 0.0,
                "total_duration_seconds": 0.0,
                "occurred_at": "2026-04-21T04:00:00+00:00",
            }
        )
        assert ok is False


class TestBackupFailureTask:
    def test_sends_error_message(self, fake_client):
        from koel.tasks.notify import slack_backup_failure_task

        ok = slack_backup_failure_task.run(
            {"error": "connection refused", "occurred_at": "2026-04-21T04:00:00+00:00"}
        )
        assert ok is True
        assert "connection refused" in fake_client.sent[0].text

    def test_unconfigured_is_noop(self, monkeypatch: pytest.MonkeyPatch):
        unset = FakeSlackClient(configured=False)
        monkeypatch.setattr("koel.tasks.notify.slack_client_from_settings", lambda: unset)
        from koel.tasks.notify import slack_backup_failure_task

        ok = slack_backup_failure_task.run({"error": "boom", "occurred_at": ""})
        assert ok is False
