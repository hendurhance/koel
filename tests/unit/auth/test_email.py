from __future__ import annotations

import pytest
from koel.auth.email import SmtpConfig, render_magic_link_email, send_magic_link


def _config(**overrides) -> SmtpConfig:
    defaults = {
        "host": "smtp.test",
        "port": 587,
        "username": "u",
        "password": "p",
        "sender": "no-reply@test",
        "use_tls": True,
    }
    defaults.update(overrides)
    return SmtpConfig(**defaults)


def _part(msg, subtype):
    return msg.get_body(preferencelist=(subtype,)).get_content()


class TestRender:
    def test_text_part_contains_link_and_ttl(self):
        msg = render_magic_link_email("u@test", "https://x/auth/verify?token=abc", ttl_minutes=15)
        text = _part(msg, "plain")
        assert "https://x/auth/verify?token=abc" in text
        assert "15 minutes" in text

    def test_html_part_contains_link(self):
        msg = render_magic_link_email("u@test", "https://x/auth/verify?token=abc", ttl_minutes=15)
        html = _part(msg, "html")
        assert "https://x/auth/verify?token=abc" in html
        assert "<html" in html.lower()

    def test_sets_headers(self):
        msg = render_magic_link_email("u@test", "https://x", ttl_minutes=10)
        assert msg["To"] == "u@test"
        assert "Koel" in msg["Subject"]


class TestIsConfigured:
    def test_fully_populated(self):
        assert _config().is_configured is True

    def test_missing_host(self):
        assert _config(host="").is_configured is False

    def test_missing_sender(self):
        assert _config(sender="").is_configured is False


class TestSendMagicLinkGuards:
    async def test_raises_when_smtp_unconfigured(self):
        with pytest.raises(RuntimeError, match="SMTP"):
            await send_magic_link("u@test", "https://x", ttl_minutes=15, config=_config(host=""))
