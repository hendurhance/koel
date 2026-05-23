from __future__ import annotations

from koel.db.partitions import drop_expired_partitions, ensure_partitions
from koel.db.session import get_engine
from koel.observability.logging import get_logger
from koel.tasks.celery_app import celery_app

log = get_logger("koel.tasks.maintenance")


@celery_app.task(name="koel.tasks.maintenance.ensure_partitions")
def ensure_partitions_task(lookahead: int = 2) -> dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        created = ensure_partitions(conn, lookahead=lookahead)
    log.info("maintenance.partitions.ensured", count=len(created))
    return {"ensured": len(created), "tables": created}


@celery_app.task(name="koel.tasks.maintenance.drop_old_partitions")
def drop_old_partitions_task() -> dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        dropped = drop_expired_partitions(conn)
    if dropped:
        log.info("maintenance.partitions.dropped", count=len(dropped), tables=dropped)
    return {"dropped": len(dropped), "tables": dropped}
