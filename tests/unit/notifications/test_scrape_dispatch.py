from __future__ import annotations

from typing import Any

import pytest
from koel.tasks.scrape import _dispatch_circuit_alerts


class _StubTask:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def delay(self, payload):
        self.calls.append(payload)


@pytest.fixture
def stub_task(monkeypatch: pytest.MonkeyPatch):
    stub = _StubTask()
    from koel.tasks import notify

    monkeypatch.setattr(notify, "slack_circuit_transition_task", stub)
    return stub


@pytest.fixture
def slack_on(monkeypatch: pytest.MonkeyPatch):
    from koel.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "SLACK_NOTIFY_ON_CIRCUIT", True)


@pytest.fixture
def slack_off(monkeypatch: pytest.MonkeyPatch):
    from koel.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "SLACK_NOTIFY_ON_CIRCUIT", False)


class TestDispatch:
    def test_dispatches_open_and_recovery(self, stub_task, slack_on):
        _dispatch_circuit_alerts(
            [
                {
                    "source_slug": "a",
                    "from_status": "closed",
                    "to_status": "open",
                    "consecutive_failures": 5,
                    "opened_at": "2026-04-20T12:00:00+00:00",
                },
                {
                    "source_slug": "b",
                    "from_status": "half_open",
                    "to_status": "closed",
                    "consecutive_failures": 0,
                    "opened_at": None,
                },
            ]
        )
        slugs = [c["source_slug"] for c in stub_task.calls]
        assert slugs == ["a", "b"]

    def test_skips_probe_flips(self, stub_task, slack_on):
        _dispatch_circuit_alerts(
            [
                {
                    "source_slug": "a",
                    "from_status": "open",
                    "to_status": "half_open",
                    "consecutive_failures": 5,
                    "opened_at": "2026-04-20T12:00:00+00:00",
                }
            ]
        )
        assert stub_task.calls == []

    def test_respects_setting_off(self, stub_task, slack_off):
        _dispatch_circuit_alerts(
            [
                {
                    "source_slug": "a",
                    "from_status": "closed",
                    "to_status": "open",
                    "consecutive_failures": 5,
                    "opened_at": "2026-04-20T12:00:00+00:00",
                }
            ]
        )
        assert stub_task.calls == []

    def test_empty_transitions_is_noop(self, stub_task, slack_on):
        _dispatch_circuit_alerts([])
        assert stub_task.calls == []
