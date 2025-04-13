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
            return [CurrencySchema.model_validate(item) for item in cached_data]
        
        currencies = db.query(Currency).all()
        if not currencies:
            raise NotFoundException("No currencies found.")

        result = [CurrencySchema.model_validate(currency) for currency in currencies]

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

        CacheManager.set(cache_key, CurrencySchema.model_validate(currency).dict(), expire=86400)
        return currency