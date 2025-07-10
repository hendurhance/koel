from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

try:
    from pydantic import ConfigDict
    PYDANTIC_V2 = True
except ImportError:
    PYDANTIC_V2 = False

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

    if PYDANTIC_V2:
        model_config = {"from_attributes": True}
    else:
        class Config:
            orm_mode = True

class ExchangeRateSchema(BaseModel):
    id: int
    base_currency_id: int
    target_currency_id: int
    rate: float
    source: str
    created_at: datetime

    if PYDANTIC_V2:
        model_config = {"from_attributes": True}
    else:
        class Config:
            orm_mode = True

class ExchangeRateWithCurrencySchema(ExchangeRateSchema):
    base_currency: CurrencySchema
    target_currency: CurrencySchema
    amount: Optional[Decimal] = None
    converted_amount: Optional[Decimal] = None

    if PYDANTIC_V2:
        model_config = {"from_attributes": True}
    else:
        class Config:
            orm_mode = True

class ExchangeRateHistorySchema(BaseModel):
    base: str
    target: str
    rates: List[ExchangeRateSchema]

    if PYDANTIC_V2:
        model_config = {"from_attributes": True}
    else:
        class Config:
            orm_mode = True