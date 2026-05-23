from __future__ import annotations

import time

from celery import Task
from redis import Redis

from koel.config import get_settings
from koel.db.session import session_scope
from koel.observability.logging import get_logger
from koel.observability.metrics import (
    usage_events_flushed_total,
    usage_flush_duration_seconds,
)
from koel.tasks.celery_app import celery_app
from koel.usage.flush import flush_stream

log = get_logger("koel.tasks.usage")


@celery_app.task(
    name="koel.tasks.usage.flush_usage_events",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def flush_usage_events_task(self: Task, batch_size: int | None = None) -> dict[str, object]:
    del self
    settings = get_settings()
    size = batch_size or settings.USAGE_FLUSH_BATCH_SIZE
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)

    started = time.perf_counter()
    with session_scope() as session:
        result = flush_stream(session, redis, batch_size=size)
    usage_flush_duration_seconds.observe(time.perf_counter() - started)
    if result.flushed:
        usage_events_flushed_total.inc(result.flushed)
        log.info(
            "usage.flush.ok",
            flushed=result.flushed,
            from_id=result.from_id,
            to_id=result.to_id,
        )
    return {
        "flushed": result.flushed,
        "from_id": result.from_id,
        "to_id": result.to_id,
    }
