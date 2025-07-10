import pytest
from pydantic import ValidationError
from app.core.config import Config

@pytest.mark.unit
class TestConfig:
    
    def test_default_config(self):
        """Test default configuration values"""
        from unittest.mock import patch
        
        # Mock the environment to ignore .env file
        with patch.dict('os.environ', {}, clear=True):
            config = Config()
            
            assert config.API_VERSION == "0.1.0"
            assert config.API_TITLE == "Koel Exchange Rate API"
            assert config.DB_CONNECTION == "postgresql"
            assert config.DB_HOST == "localhost"
            assert config.DB_PORT == 5432
            assert config.DB_USER == "postgres"
            # Password may come from .env file, so just check it's a string
            assert isinstance(config.DB_PASSWORD, str)
            assert len(config.DB_PASSWORD) > 0
            assert config.DB_NAME == "koel"
            assert config.REDIS_HOST == "localhost"
            assert config.REDIS_PORT == 6379
            # REDIS_DB may come from .env file, just check it's an integer
            assert isinstance(config.REDIS_DB, int)
            assert config.REDIS_DB >= 0

    def test_db_url_postgresql(self):
        """Test PostgreSQL database URL generation"""
        config = Config()
        config.DB_CONNECTION = "postgresql"
        config.DB_USER = "testuser"
        config.DB_PASSWORD = "testpass"
        config.DB_HOST = "testhost"
        config.DB_PORT = 5432
        config.DB_NAME = "testdb"
        
        expected_url = "postgresql://testuser:testpass@testhost:5432/testdb"
        assert config.db_url == expected_url

    def test_db_url_mysql(self):
        """Test MySQL database URL generation"""
        config = Config()
        config.DB_CONNECTION = "mysql"
        config.DB_USER = "testuser"
        config.DB_PASSWORD = "testpass"
        config.DB_HOST = "testhost"
        config.DB_PORT = 3306
        config.DB_NAME = "testdb"
        
        expected_url = "mysql://testuser:testpass@testhost:3306/testdb"
        assert config.db_url == expected_url

    def test_db_url_sqlite(self):
        """Test SQLite database URL generation"""
        config = Config()
        config.DB_CONNECTION = "sqlite"
        config.DB_NAME = "testdb.sqlite"
        
        expected_url = "sqlite:///testdb.sqlite"
        assert config.db_url == expected_url

    def test_db_url_password_encoding(self):
        """Test database URL with special characters in password"""
        config = Config()
        config.DB_CONNECTION = "postgresql"
        config.DB_USER = "testuser"
        config.DB_PASSWORD = "pass@word#123"
        config.DB_HOST = "testhost"
        config.DB_PORT = 5432
        config.DB_NAME = "testdb"
        
        # Password should be URL encoded
        expected_url = "postgresql://testuser:pass%40word%23123@testhost:5432/testdb"
        assert config.db_url == expected_url

    def test_invalid_db_connection(self):
        """Test invalid database connection type"""
        with pytest.raises(ValidationError):
            Config(DB_CONNECTION="unsupported")

    def test_unsupported_db_url(self):
        """Test unsupported database connection in db_url property"""
        config = Config()
        config.DB_CONNECTION = "oracle"  # Set directly to bypass validation
        
        with pytest.raises(ValueError, match="Unsupported DB_CONNECTION: oracle"):
            _ = config.db_url

    def test_api_properties(self):
        """Test API title and version properties"""
        config = Config()
        config.API_TITLE = "Custom API Title"
        config.API_VERSION = "2.0.0"
        
        assert config.api_title == "Custom API Title"
        assert config.api_version == "2.0.0"