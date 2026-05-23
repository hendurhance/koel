from __future__ import annotations

from typing import Any

import pytest
from koel.notifications.slack import SlackClient, SlackMessage


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


class TestSlackClient:
    def test_unconfigured_is_noop(self):
        # No URL == caller forgot to set SLACK_WEBHOOK_URL. Return False, don't
        # raise — sites with no Slack should not error on every send attempt.
        c = SlackClient(webhook_url="")
        assert c.is_configured is False
        assert c.send(SlackMessage(text="hello")) is False

    def test_send_posts_json(self, monkeypatch: pytest.MonkeyPatch):
        calls: list[dict[str, Any]] = []

        def fake_post(url, json, timeout):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse(200)

        monkeypatch.setattr("koel.notifications.slack.httpx.post", fake_post)
        c = SlackClient(webhook_url="https://hooks.slack.com/services/XXX")
        ok = c.send(SlackMessage(text="hi", blocks=[{"type": "section"}]))
        assert ok is True
        assert len(calls) == 1
        assert calls[0]["url"] == "https://hooks.slack.com/services/XXX"
        assert calls[0]["json"]["text"] == "hi"
        assert calls[0]["json"]["blocks"] == [{"type": "section"}]

    def test_send_returns_false_on_non_2xx(self, monkeypatch: pytest.MonkeyPatch):
        def fake_post(url, json, timeout):
            del url, json, timeout
            return FakeResponse(500)

        monkeypatch.setattr("koel.notifications.slack.httpx.post", fake_post)
        c = SlackClient(webhook_url="https://hooks.slack.com/services/XXX")
        assert c.send(SlackMessage(text="hi")) is False

    def test_no_blocks_field_when_empty(self):
        # Slack rejects payloads with an empty "blocks" array — we drop it.
        msg = SlackMessage(text="plain")
        assert "blocks" not in msg.to_payload()
