from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from koel.notifications.slack import SlackMessage


@dataclass(frozen=True, slots=True)
class CrawlCycleSummary:
    enqueued: int
    scraped: int
    had_consensus: int
    circuit_transitions: int
    duration_seconds: float
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class CircuitTransition:
    source_slug: str
    from_status: str
    to_status: str
    consecutive_failures: int
    opened_at: datetime | None


@dataclass(frozen=True, slots=True)
class BackupSuccess:
    filename: str
    bucket: str
    key: str
    size_bytes: int
    duration_seconds: float
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class BackupFailure:
    error: str
    occurred_at: datetime


def _format_bytes(n: int) -> str:
    # MB is the right unit for a dump file; if someone ever has a
    # >1TB Koel database, formatting precision is the least of their worries.
    return f"{n / 1024 / 1024:.1f} MB" if n else "0 MB"


def format_crawl_complete(summary: CrawlCycleSummary) -> SlackMessage:
    text = (
        f":satellite: Crawl cycle complete — "
        f"{summary.scraped}/{summary.enqueued} pairs scraped, "
        f"{summary.had_consensus} reached consensus "
        f"(in {summary.duration_seconds:.1f}s)"
    )
    fields = [
        {"type": "mrkdwn", "text": f"*Enqueued*\n{summary.enqueued}"},
        {"type": "mrkdwn", "text": f"*Scraped*\n{summary.scraped}"},
        {"type": "mrkdwn", "text": f"*Consensus*\n{summary.had_consensus}"},
        {"type": "mrkdwn", "text": f"*Circuit transitions*\n{summary.circuit_transitions}"},
        {"type": "mrkdwn", "text": f"*Duration*\n{summary.duration_seconds:.1f}s"},
        {"type": "mrkdwn", "text": f"*Finished*\n{summary.occurred_at.isoformat()}"},
    ]
    return SlackMessage(
        text=text,
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            },
            {"type": "section", "fields": fields},
        ],
    )


def format_circuit_opened(t: CircuitTransition) -> SlackMessage:
    text = (
        f":rotating_light: Circuit *opened* for `{t.source_slug}` — "
        f"{t.consecutive_failures} consecutive failures"
    )
    return SlackMessage(
        text=text,
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Source*\n`{t.source_slug}`"},
                    {"type": "mrkdwn", "text": f"*Failures*\n{t.consecutive_failures}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Opened at*\n{t.opened_at.isoformat() if t.opened_at else '—'}",
                    },
                ],
            },
        ],
    )


def format_circuit_closed(t: CircuitTransition) -> SlackMessage:
    text = f":white_check_mark: Circuit *recovered* for `{t.source_slug}`"
    return SlackMessage(
        text=text,
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ],
    )


def format_backup_success(b: BackupSuccess) -> SlackMessage:
    text = (
        f":package: Backup uploaded — `{b.filename}` "
        f"({_format_bytes(b.size_bytes)} in {b.duration_seconds:.1f}s)"
    )
    return SlackMessage(
        text=text,
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Bucket*\n`{b.bucket}`"},
                    {"type": "mrkdwn", "text": f"*Key*\n`{b.key}`"},
                    {"type": "mrkdwn", "text": f"*Size*\n{_format_bytes(b.size_bytes)}"},
                    {"type": "mrkdwn", "text": f"*Duration*\n{b.duration_seconds:.1f}s"},
                    {"type": "mrkdwn", "text": f"*Finished*\n{b.occurred_at.isoformat()}"},
                ],
            },
        ],
    )


def format_backup_failure(f: BackupFailure) -> SlackMessage:
    text = f":rotating_light: Backup *failed* — {f.error[:300]}"
    return SlackMessage(
        text=text,
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Failed at*\n{f.occurred_at.isoformat()}"},
                ],
            },
        ],
    )


__all__ = [
    "BackupFailure",
    "BackupSuccess",
    "CircuitTransition",
    "CrawlCycleSummary",
    "format_backup_failure",
    "format_backup_success",
    "format_circuit_closed",
    "format_circuit_opened",
    "format_crawl_complete",
]
