import pytest
from unittest.mock import MagicMock, patch
from app.controllers.currency_controller import CurrencyController
from app.models.models import Currency
from app.exceptions import NotFoundException

@pytest.mark.unit
class TestCurrencyController:
    
    def test_list_currencies_success(self, test_db, sample_currencies, mock_cache_manager):
        """Test successful currency listing"""
        # Mock cache to return None so it hits the database
        mock_cache_manager.get.return_value = None
        
        result = CurrencyController.list_currencies(test_db)
        
        assert len(result) == 3
        assert result[0].code == "USD"
        assert result[1].code == "EUR"
        assert result[2].code == "GBP"

    def test_list_currencies_empty_database(self, test_db):
        """Test currency listing with empty database"""
        with patch("app.controllers.currency_controller.CacheManager") as mock_cache:
            # Mock cache to return None so it hits the database
            mock_cache.get.return_value = None
            
            with pytest.raises(NotFoundException, match="No currencies found"):
                CurrencyController.list_currencies(test_db)

    def test_list_currencies_with_cache(self, test_db):
        """Test currency listing with cache hit"""
        cached_data = [
            {
                "id": 1,
                "name": "US Dollar",
                "name_plural": "US dollars",
                "code": "USD",
                "symbol": "$",
                "decimal_digits": 2,
                "icon": None,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        ]
        
        with patch("app.controllers.currency_controller.CacheManager") as mock_cache:
            mock_cache.get.return_value = cached_data
            
            result = CurrencyController.list_currencies(test_db)
            
            assert len(result) == 1
            assert result[0].code == "USD"
            mock_cache.get.assert_called_once_with("currencies:all")

    def test_get_currency_by_code_success(self, test_db, sample_currencies, mock_cache_manager):
        """Test successful currency retrieval by code"""
        result = CurrencyController.get_currency_by_code(test_db, "USD")
        
        assert result.code == "USD"
        assert result.name == "US Dollar"

    def test_get_currency_by_code_case_insensitive(self, test_db, sample_currencies, mock_cache_manager):
        """Test currency retrieval is case insensitive"""
        result = CurrencyController.get_currency_by_code(test_db, "usd")
        
        assert result.code == "USD"
        assert result.name == "US Dollar"

    def test_get_currency_by_code_not_found(self, test_db, mock_cache_manager):
        """Test currency retrieval with non-existent code"""
        with pytest.raises(NotFoundException, match="Currency 'XYZ' not found"):
            CurrencyController.get_currency_by_code(test_db, "XYZ")

    def test_get_currency_by_code_with_cache(self, test_db, sample_currencies):
        """Test currency retrieval with cache hit"""
        cached_data = {"id": 1}
        
        with patch("app.controllers.currency_controller.CacheManager") as mock_cache:
            mock_cache.get.return_value = cached_data
            
            result = CurrencyController.get_currency_by_code(test_db, "USD")
            
            assert result.id == 1
            mock_cache.get.assert_called_with("currency:USD")