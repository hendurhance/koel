from typing import List
from sqlalchemy.orm import Session
from app.models.models import Currency
from app.schemas.schema import CurrencySchema
from app.exceptions import NotFoundException
from app.utils.cache_manager import CacheManager

class CurrencyController:
    @staticmethod
    def list_currencies(db: Session) -> List[CurrencySchema]:
        """Get all currencies from the database with caching."""
        cache_key = "currencies:all"
        cached_data = CacheManager.get(cache_key)
        if cached_data:
            try:
                return [CurrencySchema.model_validate(item) for item in cached_data]
            except AttributeError:
                return [CurrencySchema(**item) for item in cached_data]
        
        currencies = db.query(Currency).all()
        if not currencies:
            raise NotFoundException("No currencies found.")

        try:
            result = [CurrencySchema.model_validate(currency) for currency in currencies]
        except AttributeError:
            result = [CurrencySchema.from_orm(currency) for currency in currencies]

        try:
            CacheManager.set(cache_key, [item.model_dump() for item in result], expire=86400)
        except AttributeError:
            CacheManager.set(cache_key, [item.dict() for item in result], expire=86400)
        return result

    @staticmethod
    def get_currency_by_code(db: Session, code: str) -> Currency:
        cache_key = f"currency:{code.upper()}"
        cached_data = CacheManager.get(cache_key)
        if cached_data and "id" in cached_data:
            return db.get(Currency, cached_data["id"])
        
        currency = db.query(Currency).filter(Currency.code == code.upper()).first()
        if not currency:
            raise NotFoundException(f"Currency '{code.upper()}' not found.")

        try:
            schema = CurrencySchema.model_validate(currency)
            CacheManager.set(cache_key, schema.model_dump(), expire=86400)
        except AttributeError:
            schema = CurrencySchema.from_orm(currency)
            CacheManager.set(cache_key, schema.dict(), expire=86400)
        return currency