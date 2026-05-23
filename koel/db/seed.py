from __future__ import annotations

import json
from importlib import resources
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from koel.db.models import Currency, Source, SourceHealth
from koel.observability.logging import get_logger

log = get_logger("koel.db.seed")


def _load(name: str) -> list[dict[str, Any]]:
    data = resources.files("koel.data").joinpath(name).read_text(encoding="utf-8")
    loaded: list[dict[str, Any]] = json.loads(data)
    return loaded


def seed_currencies(session: Session) -> int:
    rows = _load("currencies.json")
    stmt = pg_insert(Currency).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Currency.code],
        set_={
            "name": stmt.excluded.name,
            "symbol": stmt.excluded.symbol,
            "decimal_digits": stmt.excluded.decimal_digits,
            "tier": stmt.excluded.tier,
        },
    )
    session.execute(stmt)
    log.info("seed.currencies", count=len(rows))
    return len(rows)


def seed_sources(session: Session) -> int:
    rows = _load("sources.json")
    stmt = pg_insert(Source).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Source.slug],
        set_={
            "name": stmt.excluded.name,
            "base_url": stmt.excluded.base_url,
            "weight": stmt.excluded.weight,
            "config": stmt.excluded.config,
        },
    )
    session.execute(stmt)

    # Ensure a health row per source.
    source_ids = session.query(Source.id).all()
    health_rows = [{"source_id": sid} for (sid,) in source_ids]
    if health_rows:
        hstmt = pg_insert(SourceHealth).values(health_rows)
        hstmt = hstmt.on_conflict_do_nothing(index_elements=[SourceHealth.source_id])
        session.execute(hstmt)

    log.info("seed.sources", count=len(rows))
    return len(rows)


def seed_all(session: Session) -> dict[str, int]:
    return {
        "currencies": seed_currencies(session),
        "sources": seed_sources(session),
    }
