import pytest
import os
import tempfile
import sqlite3
from typing import Generator
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.db.database import Base, get_db
from app.models.models import Currency, ExchangeRate
from app.core.config import Config

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_config():
    """Test configuration"""
    config = Config()
    config.DB_CONNECTION = "sqlite"
    config.DB_NAME = ":memory:"
    config.REDIS_HOST = "localhost"
    config.REDIS_PORT = 6379
    config.REDIS_DB = 1
    config.REDIS_PASSWORD = ""
    return config

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up tables after each test
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
            db.commit()

@pytest.fixture(scope="function")
def override_get_db(test_db):
    """Override the get_db dependency"""
    def _override_get_db():
        try:
            yield test_db
        finally:
            pass
    return _override_get_db

@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client using fakeredis"""
    try:
        import fakeredis
        return fakeredis.FakeRedis()
    except ImportError:
        # Fallback to simple mock if fakeredis not available
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        mock.delete.return_value = True
        return mock

@pytest.fixture(scope="function")
def sample_currencies(test_db):
    """Create sample currencies for testing"""
    currencies = [
        Currency(
            id=1,
            name="US Dollar",
            name_plural="US dollars",
            code="USD",
            symbol="$",
            decimal_digits=2,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 1)
        ),
        Currency(
            id=2,
            name="Euro",
            name_plural="euros",
            code="EUR",
            symbol="€",
            decimal_digits=2,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 1)
        ),
        Currency(
            id=3,
            name="British Pound",
            name_plural="pounds",
            code="GBP",
            symbol="£",
            decimal_digits=2,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 1)
        )
    ]
    
    for currency in currencies:
        test_db.add(currency)
    test_db.commit()
    return currencies

@pytest.fixture(scope="function")
def sample_exchange_rates(test_db, sample_currencies):
    """Create sample exchange rates for testing"""
    rates = [
        ExchangeRate(
            id=1,
            base_currency_id=1,  # USD
            target_currency_id=2,  # EUR
            rate=0.85,
            source="test-source",
            created_at=datetime(2023, 1, 1)
        ),
        ExchangeRate(
            id=2,
            base_currency_id=1,  # USD
            target_currency_id=3,  # GBP
            rate=0.75,
            source="test-source",
            created_at=datetime(2023, 1, 1)
        ),
        ExchangeRate(
            id=3,
            base_currency_id=2,  # EUR
            target_currency_id=1,  # USD
            rate=1.18,
            source="test-source",
            created_at=datetime(2023, 1, 1)
        )
    ]
    
    for rate in rates:
        test_db.add(rate)
    test_db.commit()
    return rates

@pytest.fixture
def mock_cache_manager():
    """Mock the CacheManager"""
    with patch("app.utils.cache_manager.CacheManager") as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = None
        mock_cache.delete.return_value = None
        yield mock_cache

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for cache manager"""
    with patch("app.utils.cache_manager.redis_client") as mock_client:
        mock_client.get.return_value = None
        mock_client.setex.return_value = True
        mock_client.delete.return_value = True
        yield mock_client