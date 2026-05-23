from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from celery import Task

from koel.auth.email import send_magic_link, smtp_config_from_settings
from koel.notifications.messages import (
    BackupFailure,
    BackupSuccess,
    CircuitTransition,
    CrawlCycleSummary,
    format_backup_failure,
    format_backup_success,
    format_circuit_closed,
    format_circuit_opened,
    format_crawl_complete,
)
from koel.notifications.slack import slack_client_from_settings
from koel.observability.logging import get_logger
from koel.tasks.celery_app import celery_app

log = get_logger("koel.tasks.notify")


@celery_app.task(
    name="koel.tasks.notify.send_magic_link",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def send_magic_link_task(self: Task, recipient: str, link_url: str, ttl_minutes: int) -> None:
    """Deliver a magic-link email via SMTP. Retries on transient SMTP errors."""
    del self

    config = smtp_config_from_settings()
    log.info(
        "notify.magic_link.send",
        recipient=recipient,
        smtp_host=config.host,
        configured=config.is_configured,
    )
    asyncio.run(
        send_magic_link(
            recipient,
            link_url,
            ttl_minutes=ttl_minutes,
            config=config,
        )
    )


def _parse_opened_at(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


@celery_app.task(
    name="koel.tasks.notify.slack_circuit_transition",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def slack_circuit_transition_task(self: Task, transition: dict[str, Any]) -> bool:
    """Post a Slack alert when a source's circuit flips.

    We only notify on the transitions a human cares about: the source broke
    (``* → open``), or it recovered (``open|half_open → closed``). Probe
    flips (``open → half_open``) are too chatty.
    """
    del self

    client = slack_client_from_settings()
    if not client.is_configured:
        return False

    t = CircuitTransition(
        source_slug=transition["source_slug"],
        from_status=transition["from_status"],
        to_status=transition["to_status"],
        consecutive_failures=transition["consecutive_failures"],
        opened_at=_parse_opened_at(transition.get("opened_at")),
    )

    if t.to_status == "open":
        message = format_circuit_opened(t)
    elif t.to_status == "closed" and t.from_status in ("open", "half_open"):
        message = format_circuit_closed(t)
    else:
        return False

    sent = client.send(message)
    log.info(
        "notify.slack.circuit",
        source=t.source_slug,
        from_=t.from_status,
        to=t.to_status,
        sent=sent,
    )
    return sent


@celery_app.task(
    name="koel.tasks.notify.slack_crawl_complete",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def slack_crawl_complete_task(self: Task, summary: dict[str, Any]) -> bool:
    """Post a per-cycle summary to Slack. Gated behind ``SLACK_NOTIFY_ON_CRAWL``."""
    del self

    client = slack_client_from_settings()
    if not client.is_configured:
        return False

    s = CrawlCycleSummary(
        enqueued=summary["enqueued"],
        scraped=summary["scraped"],
        had_consensus=summary["had_consensus"],
        circuit_transitions=summary["circuit_transitions"],
        duration_seconds=summary["duration_seconds"],
        occurred_at=datetime.fromisoformat(summary["occurred_at"])
        if summary.get("occurred_at")
        else datetime.now(tz=UTC),
    )
    sent = client.send(format_crawl_complete(s))
    log.info(
        "notify.slack.crawl",
        enqueued=s.enqueued,
        scraped=s.scraped,
        sent=sent,
    )
    return sent


@celery_app.task(
    name="koel.tasks.notify.slack_backup_success",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def slack_backup_success_task(self: Task, outcome: dict[str, Any]) -> bool:
    """Post a Slack message summarizing a successful backup."""
    del self

    client = slack_client_from_settings()
    if not client.is_configured:
        return False

    b = BackupSuccess(
        filename=outcome["filename"],
        bucket=outcome["bucket"],
        key=outcome["key"],
        size_bytes=outcome["size_bytes"],
        duration_seconds=outcome["total_duration_seconds"],
        occurred_at=datetime.fromisoformat(outcome["occurred_at"])
        if outcome.get("occurred_at")
        else datetime.now(tz=UTC),
    )
    sent = client.send(format_backup_success(b))
    log.info("notify.slack.backup_success", key=b.key, sent=sent)
    return sent


@celery_app.task(
    name="koel.tasks.notify.slack_backup_failure",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def slack_backup_failure_task(self: Task, failure: dict[str, Any]) -> bool:
    """Post a Slack alert when a backup run fails."""
    del self

    client = slack_client_from_settings()
    if not client.is_configured:
        return False

    f = BackupFailure(
        error=failure.get("error", "unknown"),
        occurred_at=datetime.fromisoformat(failure["occurred_at"])
        if failure.get("occurred_at")
        else datetime.now(tz=UTC),
    )
    sent = client.send(format_backup_failure(f))
    log.info("notify.slack.backup_failure", sent=sent)
    return sent
