from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

class CurrencySchema(BaseModel):
    id: int
    name: str
    name_plural: Optional[str] = None
    code: str
    symbol: str
    decimal_digits: int
    icon: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ExchangeRateSchema(BaseModel):
    id: int
    base_currency_id: int
    target_currency_id: int
    rate: float
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

class ExchangeRateWithCurrencySchema(ExchangeRateSchema):
    base_currency: CurrencySchema
    target_currency: CurrencySchema
    amount: Optional[Decimal] = None
    converted_amount: Optional[Decimal] = None

    class Config:
        from_attributes = True

class ExchangeRateHistorySchema(BaseModel):
    base: str
    target: str
    rates: List[ExchangeRateSchema]

    class Config:
        from_attributes = True