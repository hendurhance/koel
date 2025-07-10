import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime
from decimal import Decimal

from app.utils.cache_manager import CacheManager, default_converter

@pytest.mark.unit
class TestCacheManager:
    
    def test_get_success(self, mock_redis_client):
        """Test successful cache get"""
        test_data = {"key": "value", "number": 123}
        mock_redis_client.get.return_value = json.dumps(test_data)
        
        result = CacheManager.get("test_key")
        
        assert result == test_data
        mock_redis_client.get.assert_called_once_with("test_key")

    def test_get_not_found(self, mock_redis_client):
        """Test cache get when key doesn't exist"""
        mock_redis_client.get.return_value = None
        
        result = CacheManager.get("nonexistent_key")
        
        assert result is None
        mock_redis_client.get.assert_called_once_with("nonexistent_key")

    def test_get_redis_error(self, mock_redis_client):
        """Test cache get with Redis error"""
        import redis
        mock_redis_client.get.side_effect = redis.RedisError("Connection failed")
        
        result = CacheManager.get("test_key")
        
        assert result is None

    def test_set_success(self, mock_redis_client):
        """Test successful cache set"""
        test_data = {"key": "value", "number": 123}
        
        CacheManager.set("test_key", test_data, expire=3600)
        
        mock_redis_client.setex.assert_called_once_with(
            "test_key", 3600, json.dumps(test_data, default=default_converter)
        )

    def test_set_redis_error(self, mock_redis_client):
        """Test cache set with Redis error"""
        import redis
        mock_redis_client.setex.side_effect = redis.RedisError("Connection failed")
        
        # Should not raise exception
        CacheManager.set("test_key", {"data": "value"})

    def test_delete_success(self, mock_redis_client):
        """Test successful cache delete"""
        CacheManager.delete("test_key")
        
        mock_redis_client.delete.assert_called_once_with("test_key")

    def test_default_converter_datetime(self):
        """Test default_converter with datetime object"""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        result = default_converter(dt)
        assert result == "2023-01-01T12:00:00"

    def test_default_converter_decimal(self):
        """Test default_converter with Decimal object"""
        decimal_val = Decimal("123.45")
        result = default_converter(decimal_val)
        assert result == 123.45

    def test_default_converter_unsupported_type(self):
        """Test default_converter with unsupported type"""
        with pytest.raises(TypeError):
            default_converter({"unsupported": "type"})