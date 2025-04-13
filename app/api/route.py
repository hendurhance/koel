from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from app.schemas.schema import (
    CurrencySchema,
    ExchangeRateWithCurrencySchema,
    ExchangeRateHistorySchema,
)
from app.db.database import get_db
from sqlalchemy.orm import Session
from app.schemas.api_response import success_response, ApiResponse
from app.controllers.currency_controller import CurrencyController
from app.controllers.exchange_rate_controller import ExchangeRateController

router = APIRouter()


@router.get("/currencies", response_model=ApiResponse[List[CurrencySchema]])
async def list_currencies(db: Session = Depends(get_db)):
    """List all available currencies."""
    currencies = CurrencyController.list_currencies(db)
    return success_response(
        data=currencies, message="Currencies retrieved successfully."
    )


@router.get("/rates", response_model=ApiResponse[ExchangeRateWithCurrencySchema])
async def get_exchange_rate(
    base: str,
    target: str,
    amount: Optional[Decimal] = None,
    db: Session = Depends(get_db),
):
    """Get the current exchange rate between two currencies with optional amount conversion."""
    result = ExchangeRateController.get_current_rate(db, base, target, amount)
    return success_response(
        data=result, message="Exchange rate retrieved successfully."
    )


@router.get("/rates/history", response_model=ApiResponse[ExchangeRateHistorySchema])
async def get_exchange_rate_history(
    base: str,
    target: str,
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    """Get exchange rate history between two currencies for a date range."""
    result = ExchangeRateController.get_rate_history(
        db, base, target, from_date, to_date
    )
    return success_response(
        data=result, message="Exchange rate history retrieved successfully."
    )