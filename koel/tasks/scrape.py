from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from celery import Task

from koel.config import get_settings
from koel.db.repositories import (
    filter_callable_sources,
    get_due_pairs,
    get_source_specs,
    materialize_cross_rates,
    persist_pair_outcome,
    resolve_currency_ids,
)
from koel.db.session import session_scope
from koel.observability.logging import get_logger
from koel.observability.metrics import (
    circuit_transitions_total,
    scrape_pairs_total,
)
from koel.scraping.client import ScrapeClient
from koel.scraping.service import (
    PairOutcome,
    SourceSpec,
)
from koel.scraping.service import scrape_pair as service_scrape_pair
from koel.tasks.celery_app import celery_app

log = get_logger("koel.tasks.scrape")


@celery_app.task(name="koel.tasks.scrape.dispatch_cycle")
def dispatch_cycle_task() -> dict[str, object]:
    """Beat entrypoint. Finds due pairs and enqueues one scrape per pair.

    Optionally fans out a Slack cycle-summary (off by default — flip
    ``SLACK_NOTIFY_ON_CRAWL=True`` to opt in). The summary reports what
    *dispatch* did; per-pair outcomes land from ``scrape_pair_task``.
    """
    started_at = time.perf_counter()
    now = datetime.now(tz=UTC)
    with session_scope() as session:
        due = get_due_pairs(session, now)

    for pair in due:
        scrape_pair_task.delay(pair.base_code, pair.target_code)

    duration = time.perf_counter() - started_at
    log.info("scrape.dispatch.cycle", enqueued=len(due), duration_seconds=round(duration, 3))

    settings = get_settings()
    if settings.SLACK_NOTIFY_ON_CRAWL and len(due) > 0:
        # Local import dodges an import cycle between scrape <-> notify.
        from koel.tasks.notify import slack_crawl_complete_task

        slack_crawl_complete_task.delay(
            {
                "enqueued": len(due),
                # ``dispatch_cycle`` doesn't wait for pair results, so ``scraped``
                # and downstream metrics aren't known here. Reporting enqueued
                # counts keeps the payload honest.
                "scraped": len(due),
                "had_consensus": 0,
                "circuit_transitions": 0,
                "duration_seconds": duration,
                "occurred_at": now.isoformat(),
            }
        )
    return {"enqueued": len(due)}


@celery_app.task(
    name="koel.tasks.scrape.scrape_pair",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def scrape_pair_task(self: Task, base_code: str, target_code: str) -> dict[str, object]:
    """Run the full pipeline for one (base, target) pair."""
    del self  # Celery binds but we don't need retry-handle here.
    now = datetime.now(tz=UTC)

    with session_scope() as session:
        ids = resolve_currency_ids(session, [base_code, target_code])
        if base_code not in ids or target_code not in ids:
            log.warning(
                "scrape.pair.unknown_currency",
                base=base_code,
                target=target_code,
                resolved=list(ids.keys()),
            )
            scrape_pairs_total.labels(outcome="unknown_pair").inc()
            return {"skipped": "unknown currency"}
        base_id = ids[base_code]
        target_id = ids[target_code]
        specs = filter_callable_sources(session, get_source_specs(session), now)

    if not specs:
        log.warning("scrape.pair.no_callable_sources", base=base_code, target=target_code)
        scrape_pairs_total.labels(outcome="no_sources").inc()
        return {"skipped": "no callable sources"}

    outcome = asyncio.run(_run_scrape(base_code, target_code, specs))

    with session_scope() as session:
        summary = persist_pair_outcome(
            session,
            outcome,
            base_id=base_id,
            target_id=target_id,
            now=now,
        )

    transitions = cast("list[dict[str, object]]", summary.get("transitions", []))
    _dispatch_circuit_alerts(transitions)
    _observe_circuit_metrics(transitions)
    scrape_pairs_total.labels(
        outcome="consensus" if outcome.consensus is not None else "no_consensus"
    ).inc()

    log.info(
        "scrape.pair.done",
        base=base_code,
        target=target_code,
        has_consensus=outcome.consensus is not None,
        **summary,
    )
    return {
        "base": base_code,
        "target": target_code,
        "consensus_rate": str(outcome.consensus.rate) if outcome.consensus else None,
        **summary,
    }


def _observe_circuit_metrics(transitions: list[dict[str, object]]) -> None:
    for t in transitions:
        circuit_transitions_total.labels(
            source=str(t.get("source_slug") or "unknown"),
            from_status=str(t.get("from_status") or "unknown"),
            to_status=str(t.get("to_status") or "unknown"),
        ).inc()


def _dispatch_circuit_alerts(transitions: list[dict[str, object]]) -> None:
    """Fan out a Slack alert per notable transition.

    Deferred imports avoid a scrape <-> notify cycle; Celery itself decides
    whether the task actually emits (webhook may be unset, etc.).
    """
    settings = get_settings()
    if not settings.SLACK_NOTIFY_ON_CIRCUIT:
        return

    from koel.tasks.notify import slack_circuit_transition_task

    for t in transitions:
        # Skip ``open -> half_open`` probe flips; they're noise.
        if t.get("to_status") == "open" or (
            t.get("to_status") == "closed" and t.get("from_status") in ("open", "half_open")
        ):
            slack_circuit_transition_task.delay(t)


@celery_app.task(name="koel.tasks.scrape.materialize_cross_rates_cycle")
def materialize_cross_rates_task() -> dict[str, object]:
    """Derive non-USD pairs from the current USD table and upsert."""
    with session_scope() as session:
        written = materialize_cross_rates(session)

    log.info("scrape.cross.materialized", written=written)
    return {"written": written}


async def _run_scrape(
    base: str,
    target: str,
    specs: Sequence[SourceSpec],
) -> PairOutcome:
    async with ScrapeClient() as client:
        return await service_scrape_pair(base, target, specs, client)
