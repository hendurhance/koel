#!/usr/bin/env python3
"""
Simple test runner to validate core functionality without complex dependencies
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    try:
        import app.main
        import app.core.config
        import app.models.models
        import app.controllers.currency_controller
        import app.controllers.exchange_rate_controller
        import app.utils.cache_manager
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_config():
    """Test configuration"""
    try:
        from app.core.config import Config
        config = Config()
        assert config.API_VERSION == "0.1.0"
        assert config.DB_CONNECTION == "postgresql"
        assert config.db_url.startswith("postgresql://")
        print("✓ Config tests passed")
        return True
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False

def test_cache_manager():
    """Test cache manager error handling"""
    try:
        from app.utils.cache_manager import CacheManager, default_converter
        from decimal import Decimal
        from datetime import datetime
        
        # Test converters
        assert default_converter(datetime(2023, 1, 1)) == "2023-01-01T00:00:00"
        assert default_converter(Decimal("123.45")) == 123.45
        
        # Test cache operations (should handle errors gracefully)
        CacheManager.get("test_key")  # Should not crash
        CacheManager.set("test_key", {"test": "value"})  # Should not crash
        CacheManager.delete("test_key")  # Should not crash
        
        print("✓ Cache manager tests passed")
        return True
    except Exception as e:
        print(f"✗ Cache manager test failed: {e}")
        return False

def test_models():
    """Test model definitions"""
    try:
        from app.models.models import Currency, ExchangeRate
        from app.db.database import Base
        
        # Check that models are properly defined
        assert hasattr(Currency, '__tablename__')
        assert hasattr(ExchangeRate, '__tablename__')
        assert Currency.__tablename__ == "currencies"
        assert ExchangeRate.__tablename__ == "exchange_rates"
        
        print("✓ Model tests passed")
        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        return False

def test_api_structure():
    """Test API structure"""
    try:
        from app.main import app
        from app.api.route import router
        
        # Check that app is properly configured
        assert app.title == "Koel Exchange Rate API"
        assert app.version == "0.1.0"
        
        print("✓ API structure tests passed")
        return True
    except Exception as e:
        print(f"✗ API structure test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Running simple functionality tests...\n")
    
    tests = [
        test_imports,
        test_config,
        test_cache_manager,
        test_models,
        test_api_structure
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())