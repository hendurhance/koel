from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache

import aiosmtplib
from jinja2 import Environment, PackageLoader, select_autoescape

APP_NAME = "Koel"


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=PackageLoader("koel", "templates/email"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.host) and bool(self.sender)


def render_magic_link_email(recipient: str, link_url: str, ttl_minutes: int) -> EmailMessage:
    ctx = {"app_name": APP_NAME, "link_url": link_url, "ttl_minutes": ttl_minutes}
    text_body = _env().get_template("magic_link.txt").render(**ctx)
    html_body = _env().get_template("magic_link.html").render(**ctx)

    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = f"Your {APP_NAME} sign-in link"
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


async def send_magic_link(
    recipient: str,
    link_url: str,
    *,
    ttl_minutes: int,
    config: SmtpConfig,
) -> None:
    """Send the magic link. Raises on SMTP failure so the caller can retry."""
    if not config.is_configured:
        raise RuntimeError("SMTP is not configured (SMTP_HOST / SMTP_FROM are empty)")

    msg = render_magic_link_email(recipient, link_url, ttl_minutes)
    msg["From"] = config.sender

    await aiosmtplib.send(
        msg,
        hostname=config.host,
        port=config.port,
        username=config.username or None,
        password=config.password or None,
        start_tls=config.use_tls,
    )


def smtp_config_from_settings() -> SmtpConfig:
    from koel.config import get_settings

    s = get_settings()
    return SmtpConfig(
        host=s.SMTP_HOST,
        port=s.SMTP_PORT,
        username=s.SMTP_USER,
        password=s.SMTP_PASSWORD,
        sender=s.SMTP_FROM,
        use_tls=s.SMTP_TLS,
    )
