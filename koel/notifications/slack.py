from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class SlackMessage:
    """A minimal Slack Incoming Webhook payload.

    ``text`` is the fallback / notification preview; ``blocks`` (if any) carry
    the rich layout. We keep the shape narrow on purpose: rich blocks are a
    Slack API surface we don't want to grow into without a reason.
    """

    text: str
    blocks: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": self.text}
        if self.blocks:
            payload["blocks"] = self.blocks
        return payload


class SlackClient:
    def __init__(self, webhook_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._webhook_url = webhook_url
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def send(self, message: SlackMessage) -> bool:
        """Post the message synchronously. Returns True on 2xx, False otherwise.

        Raises on transport errors so Celery's retry machinery can pick them
        up — non-2xx HTTP responses (a bad webhook URL, workspace rate limit)
        are not retried because they won't recover on their own.
        """
        if not self.is_configured:
            return False
        response = httpx.post(
            self._webhook_url,
            json=message.to_payload(),
            timeout=self._timeout,
        )
        return response.is_success


def slack_client_from_settings() -> SlackClient:
    from koel.config import get_settings

    settings = get_settings()
    return SlackClient(settings.SLACK_WEBHOOK_URL)


__all__ = ["SlackClient", "SlackMessage", "slack_client_from_settings"]
