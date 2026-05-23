from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from koel.api.deps import get_db, require_rates_read
from koel.api.schemas import CurrenciesResponse, CurrencyInfo
from koel.db.queries import list_active_currencies

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(tags=["metadata"], dependencies=[Depends(require_rates_read)])


@router.get("/currencies", response_model=CurrenciesResponse, summary="List active currencies")
def currencies(session: DbSession) -> CurrenciesResponse:
    rows = list_active_currencies(session)
    return CurrenciesResponse(
        currencies=[
            CurrencyInfo(
                code=r.code,
                name=r.name,
                symbol=r.symbol,
                decimal_digits=r.decimal_digits,
                tier=r.tier,
            )
            for r in rows
        ]
    )
