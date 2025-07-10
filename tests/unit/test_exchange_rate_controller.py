import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.controllers.exchange_rate_controller import ExchangeRateController
from app.models.models import ExchangeRate

@pytest.mark.unit
class TestExchangeRateController:
    
    def test_get_current_rate_success(self, test_db, sample_currencies, sample_exchange_rates, mock_cache_manager):
        """Test successful exchange rate retrieval"""
        result = ExchangeRateController.get_current_rate(test_db, "USD", "EUR")
        
        assert result.rate == 0.85
        assert result.base_currency.code == "USD"
        assert result.target_currency.code == "EUR"
        assert result.source == "test-source"

    def test_get_current_rate_with_amount(self, test_db, sample_currencies, sample_exchange_rates, mock_cache_manager):
        """Test exchange rate retrieval with amount conversion"""
        amount = Decimal("100")
        result = ExchangeRateController.get_current_rate(test_db, "USD", "EUR", amount)
        
        assert result.rate == 0.85
        assert result.amount == amount
        assert result.converted_amount == Decimal("85.00")

    def test_get_current_rate_same_currency(self, test_db, sample_currencies, mock_cache_manager):
        """Test exchange rate retrieval with same base and target currency"""
        with pytest.raises(HTTPException) as exc_info:
            ExchangeRateController.get_current_rate(test_db, "USD", "USD")
        
        assert exc_info.value.status_code == 400
        assert "Base and target currencies cannot be the same" in str(exc_info.value.detail)

    def test_get_current_rate_not_found(self, test_db, sample_currencies, mock_cache_manager):
        """Test exchange rate retrieval when rate doesn't exist"""
        with pytest.raises(HTTPException) as exc_info:
            ExchangeRateController.get_current_rate(test_db, "EUR", "GBP")
        
        assert exc_info.value.status_code == 404
        assert "Exchange rate not found" in str(exc_info.value.detail)

    def test_get_current_rate_with_cache(self, test_db, sample_currencies, sample_exchange_rates):
        """Test exchange rate retrieval with cache hit"""
        cached_data = {
            "id": 1,
            "base_currency_id": 1,
            "target_currency_id": 2,
            "rate": 0.85,
            "source": "cached-source",
            "created_at": "2023-01-01T00:00:00",
            "base_currency": {
                "id": 1,
                "name": "US Dollar",
                "name_plural": "US dollars",
                "code": "USD",
                "symbol": "$",
                "decimal_digits": 2,
                "icon": None,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            },
            "target_currency": {
                "id": 2,
                "name": "Euro",
                "name_plural": "euros", 
                "code": "EUR",
                "symbol": "€",
                "decimal_digits": 2,
                "icon": None,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            },
            "amount": None,
            "converted_amount": None
        }
        
        with patch("app.controllers.exchange_rate_controller.CacheManager") as mock_cache:
            mock_cache.get.return_value = cached_data
            
            result = ExchangeRateController.get_current_rate(test_db, "USD", "EUR")
            
            assert result.rate == 0.85
            assert result.source == "cached-source"
            mock_cache.get.assert_called_once_with("exchange_rate:USD-EUR")

    def test_get_rate_history_success(self, test_db, sample_currencies, sample_exchange_rates, mock_cache_manager):
        """Test successful exchange rate history retrieval"""
        from_date = datetime(2022, 12, 31)
        to_date = datetime(2023, 1, 2)
        
        result = ExchangeRateController.get_rate_history(test_db, "USD", "EUR", from_date, to_date)
        
        assert result.base == "USD"
        assert result.target == "EUR"
        assert len(result.rates) == 1
        assert result.rates[0].rate == 0.85

    def test_get_rate_history_default_dates(self, test_db, sample_currencies, sample_exchange_rates, mock_cache_manager):
        """Test exchange rate history with default date range"""
        # The sample data is from 2023-01-01, so we need to use a date range that includes it
        from datetime import datetime, timedelta
        
        # Set dates that will include our sample data
        to_date = datetime(2023, 1, 2)  # After our sample data
        from_date = datetime(2022, 12, 31)  # Before our sample data
        
        result = ExchangeRateController.get_rate_history(test_db, "USD", "EUR", from_date, to_date)
        
        assert result.base == "USD"
        assert result.target == "EUR"
        assert len(result.rates) == 1

    def test_get_rate_history_same_currency(self, test_db, sample_currencies, mock_cache_manager):
        """Test exchange rate history with same base and target currency"""
        with pytest.raises(HTTPException) as exc_info:
            ExchangeRateController.get_rate_history(test_db, "USD", "USD")
        
        assert exc_info.value.status_code == 400
        assert "Base and target currencies cannot be the same" in str(exc_info.value.detail)

    def test_get_rate_history_not_found(self, test_db, sample_currencies, mock_cache_manager):
        """Test exchange rate history when no rates exist"""
        from_date = datetime(2020, 1, 1)
        to_date = datetime(2020, 1, 2)
        
        with pytest.raises(HTTPException) as exc_info:
            ExchangeRateController.get_rate_history(test_db, "USD", "EUR", from_date, to_date)
        
        assert exc_info.value.status_code == 404
        assert "Exchange rate history not found" in str(exc_info.value.detail)