import pytest
from unittest.mock import patch, MagicMock
import json

@pytest.mark.integration 
class TestAPIRoutesSimple:
    """Integration tests that don't require FastAPI TestClient"""
    
    def test_currency_controller_integration(self, test_db, sample_currencies, mock_cache_manager):
        """Test currency controller with real database"""
        from app.controllers.currency_controller import CurrencyController
        
        # Test listing currencies
        currencies = CurrencyController.list_currencies(test_db)
        assert len(currencies) == 3
        assert currencies[0].code == "USD"
        
        # Test getting currency by code
        usd_currency = CurrencyController.get_currency_by_code(test_db, "USD")
        assert usd_currency.code == "USD"
        assert usd_currency.name == "US Dollar"

    def test_exchange_rate_controller_integration(self, test_db, sample_currencies, sample_exchange_rates, mock_cache_manager):
        """Test exchange rate controller with real database"""
        from app.controllers.exchange_rate_controller import ExchangeRateController
        from decimal import Decimal
        
        # Test getting current rate
        result = ExchangeRateController.get_current_rate(test_db, "USD", "EUR")
        assert result.rate == 0.85
        assert result.base_currency.code == "USD"
        assert result.target_currency.code == "EUR"
        
        # Test with amount
        result_with_amount = ExchangeRateController.get_current_rate(test_db, "USD", "EUR", Decimal("100"))
        assert result_with_amount.amount == Decimal("100")
        assert result_with_amount.converted_amount == Decimal("85.00")

    def test_api_endpoints_logic(self, test_db, sample_currencies, sample_exchange_rates, mock_cache_manager):
        """Test the logic that API endpoints would use"""
        from app.controllers.currency_controller import CurrencyController
        from app.controllers.exchange_rate_controller import ExchangeRateController
        from app.schemas.api_response import success_response
        
        # Test currencies endpoint logic
        currencies = CurrencyController.list_currencies(test_db)
        response_data = success_response(
            data=currencies, message="Currencies retrieved successfully."
        )
        assert response_data.success is True
        assert len(response_data.data) == 3
        
        # Test rates endpoint logic
        rate = ExchangeRateController.get_current_rate(test_db, "USD", "EUR")
        rate_response = success_response(
            data=rate, message="Exchange rate retrieved successfully."
        )
        assert rate_response.success is True
        assert rate_response.data.rate == 0.85

    def test_error_handling(self, test_db, mock_cache_manager):
        """Test error handling in controllers"""
        from app.controllers.currency_controller import CurrencyController
        from app.controllers.exchange_rate_controller import ExchangeRateController
        from app.exceptions import NotFoundException
        from fastapi import HTTPException
        
        # Test currency not found
        with pytest.raises(NotFoundException):
            CurrencyController.get_currency_by_code(test_db, "XYZ")
        
        # Test same currency error
        with pytest.raises(HTTPException) as exc_info:
            ExchangeRateController.get_current_rate(test_db, "USD", "USD")
        assert exc_info.value.status_code == 400

    def test_cache_integration(self, test_db, sample_currencies):
        """Test that caching works in controllers"""
        from app.controllers.currency_controller import CurrencyController
        
        with patch("app.controllers.currency_controller.CacheManager") as mock_cache:
            # First call - should hit database and set cache
            mock_cache.get.return_value = None
            currencies = CurrencyController.list_currencies(test_db)
            
            # Verify cache was called
            mock_cache.get.assert_called_with("currencies:all")
            mock_cache.set.assert_called_once()
            assert len(currencies) == 3

    def test_validation_logic(self, test_config):
        """Test configuration validation"""
        from app.core.config import Config
        
        config = Config()
        assert config.api_title == "Koel Exchange Rate API"
        assert config.api_version == "0.1.0"
        
        # Test database URL generation
        db_url = config.db_url
        assert db_url.startswith("postgresql://")
        assert "postgres" in db_url