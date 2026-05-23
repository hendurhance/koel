from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from celery import Task

from koel.backups.orchestrator import BackupOutcome, run_backup
from koel.backups.pgdump import PgDumpRunner
from koel.backups.s3 import S3Uploader
from koel.config import get_settings
from koel.observability.logging import get_logger
from koel.observability.metrics import (
    backup_duration_seconds,
    backup_last_size_bytes,
    backup_runs_total,
)
from koel.tasks.celery_app import celery_app

log = get_logger("koel.tasks.backup")


def _build_runner() -> PgDumpRunner:
    settings = get_settings()
    return PgDumpRunner(database_url=settings.DATABASE_URL)


def _build_uploader() -> S3Uploader:
    settings = get_settings()
    return S3Uploader(
        bucket=settings.BACKUP_S3_BUCKET,
        region=settings.BACKUP_S3_REGION,
        access_key_id=settings.AWS_ACCESS_KEY_ID,
        secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        prefix=settings.BACKUP_S3_PREFIX,
    )


def _dispatch_success(outcome: BackupOutcome) -> None:
    # Local import — Slack task lives on a different queue, and the deferred
    # import mirrors the pattern used by scrape → notify.
    from koel.tasks.notify import slack_backup_success_task

    slack_backup_success_task.delay(outcome.to_dict())


def _dispatch_failure(error: str, occurred_at: datetime) -> None:
    from koel.tasks.notify import slack_backup_failure_task

    slack_backup_failure_task.delay({"error": error, "occurred_at": occurred_at.isoformat()})


@celery_app.task(
    name="koel.tasks.backup.daily_backup",
    bind=True,
    ignore_result=True,
)
def daily_backup_task(self: Task) -> dict[str, object]:
    """Run one dump + upload. No automatic retries — Slack tells the operator."""
    del self

    settings = get_settings()
    if not settings.BACKUP_ENABLED:
        log.info("backup.skipped", reason="disabled")
        backup_runs_total.labels(outcome="skipped").inc()
        return {"skipped": "disabled"}
    if not settings.BACKUP_S3_BUCKET:
        log.warning("backup.skipped", reason="no_bucket")
        backup_runs_total.labels(outcome="skipped").inc()
        return {"skipped": "no_bucket"}

    now = datetime.now(tz=UTC)
    try:
        outcome = asyncio.run(run_backup(_build_runner(), _build_uploader(), now=now))
    except Exception as exc:
        # Broad catch is load-bearing: any failure becomes a Slack alert and
        # then re-raises so Celery records the task as failed.
        log.exception("backup.failed", error=str(exc))
        backup_runs_total.labels(outcome="failed").inc()
        _dispatch_failure(str(exc), now)
        raise

    backup_runs_total.labels(outcome="ok").inc()
    backup_duration_seconds.observe(outcome.total_duration_seconds)
    backup_last_size_bytes.set(outcome.size_bytes)
    _dispatch_success(outcome)
    log.info("backup.done", **outcome.to_dict())
    return outcome.to_dict()
