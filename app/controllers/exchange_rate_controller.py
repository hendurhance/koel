from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException
from app.models.models import ExchangeRate
from app.schemas.schema import (
    ExchangeRateSchema,
    ExchangeRateWithCurrencySchema,
    ExchangeRateHistorySchema,
)
from app.controllers.currency_controller import CurrencyController
from app.utils.cache_manager import CacheManager
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)

class ExchangeRateController:
    @staticmethod
    def get_current_rate(
        db: Session, base_code: str, target_code: str, amount: Optional[Decimal] = None
    ) -> ExchangeRateWithCurrencySchema:
        """
        Get the most recent exchange rate between two currencies with optional amount conversion.
        """
        if base_code.upper() == target_code.upper():
            raise HTTPException(
                status_code=400, detail="Base and target currencies cannot be the same."
            )

        cache_key = f"exchange_rate:{base_code.upper()}-{target_code.upper()}"
        cached_data = CacheManager.get(cache_key)
        if cached_data:
            result = ExchangeRateWithCurrencySchema.model_validate(cached_data)
            if amount is not None:
                converted_amount = amount * Decimal(str(result.rate))
                rounded_amount = round(converted_amount, result.target_currency.decimal_digits)
                result.amount = amount
                result.converted_amount = rounded_amount
            return result

        logger.info(
            f"Fetching exchange rate for {base_code.upper()} to {target_code.upper()}"
        )

        # Get currency records
        base_currency = CurrencyController.get_currency_by_code(db, base_code)
        target_currency = CurrencyController.get_currency_by_code(db, target_code)

        # Query the most recent exchange rate
        exchange = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.base_currency_id == base_currency.id,
                ExchangeRate.target_currency_id == target_currency.id,
            )
            .order_by(desc(ExchangeRate.created_at))
            .first()
        )
        if not exchange:
            raise HTTPException(status_code=404, detail="Exchange rate not found.")

        # Set related currencies to the exchange to avoid validation errors.
        exchange.base_currency = base_currency
        exchange.target_currency = target_currency

        result = ExchangeRateWithCurrencySchema.model_validate(exchange)

        # Add conversion information if an amount is provided.
        if amount is not None:
            converted_amount = amount * Decimal(str(result.rate))
            rounded_amount = round(converted_amount, target_currency.decimal_digits)
            result.amount = amount
            result.converted_amount = rounded_amount

        CacheManager.set(cache_key, result.dict(), expire=3600)
        return result

    @staticmethod
    def get_rate_history(
        db: Session,
        base_code: str,
        target_code: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> ExchangeRateHistorySchema:
        """Get exchange rate history between two currencies for a date range."""
        if base_code.upper() == target_code.upper():
            raise HTTPException(
                status_code=400, detail="Base and target currencies cannot be the same."
            )

        # Get currency records
        base_currency = CurrencyController.get_currency_by_code(db, base_code)
        target_currency = CurrencyController.get_currency_by_code(db, target_code)

        # Set default date range if not provided
        if not to_date:
            to_date = datetime.now()
        if not from_date:
            # Default to 30 days of history if not specified
            from_date = to_date - timedelta(days=30)

        # Query the exchange rates
        rates = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.base_currency_id == base_currency.id,
                ExchangeRate.target_currency_id == target_currency.id,
                ExchangeRate.created_at >= from_date,
                ExchangeRate.created_at <= to_date,
            )
            .order_by(ExchangeRate.created_at)
            .all()
        )
        if not rates:
            raise HTTPException(
                status_code=404, detail="Exchange rate history not found."
            )

        # Convert query results to schema objects.
        rate_schemas = [
            ExchangeRateSchema(
                id=rate.id,
                base_currency_id=rate.base_currency_id,
                target_currency_id=rate.target_currency_id,
                rate=rate.rate,
                source=rate.source,
                created_at=rate.created_at,
            )
            for rate in rates
        ]

        result = ExchangeRateHistorySchema(
            base=base_code.upper(), target=target_code.upper(), rates=rate_schemas
        )
        return result
