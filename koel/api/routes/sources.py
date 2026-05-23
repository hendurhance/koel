from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from koel.api.deps import get_db, require_rates_read
from koel.api.schemas import CircuitState, SourceHealthInfo, SourceInfo, SourcesResponse
from koel.db.queries import SourceRow, list_sources_with_health

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(tags=["metadata"], dependencies=[Depends(require_rates_read)])


def _health_of(row: SourceRow) -> SourceHealthInfo | None:
    if row.circuit_state is None:
        return None
    return SourceHealthInfo(
        circuit_state=CircuitState(row.circuit_state),
        consecutive_failures=row.consecutive_failures or 0,
        total_requests=row.total_requests or 0,
        total_failures=row.total_failures or 0,
        avg_latency_ms=row.avg_latency_ms,
        last_success_at=row.last_success_at,
        last_failure_at=row.last_failure_at,
    )


@router.get("/sources", response_model=SourcesResponse, summary="List sources with health")
def sources(session: DbSession) -> SourcesResponse:
    rows = list_sources_with_health(session)
    return SourcesResponse(
        sources=[
            SourceInfo(
                slug=r.slug,
                name=r.name,
                weight=r.weight,
                is_active=r.is_active,
                health=_health_of(r),
            )
            for r in rows
        ]
    )
