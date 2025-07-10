# Testing Guide

This document explains how to run tests for the Koel Exchange Rate API.

## Quick Start (No Dependencies)

Run basic functionality tests that require no additional dependencies:

```bash
# Using Python directly
python test_local.py

# Using Makefile
make test-basic
```

This will test:
- ✅ All module imports
- ✅ Configuration system  
- ✅ Cache manager functionality
- ✅ Model definitions
- ✅ API structure

## Full Test Suite (Requires pytest)

### Install Dependencies

```bash
pip install pytest pytest-mock fakeredis
```

### Run Tests

```bash
# Run all available tests
python run_tests.py
# or
make test

# Run only unit tests
make test-unit
# or
pytest tests/unit/ -v

# Run only integration tests  
make test-integration
# or
pytest tests/integration/ -v

# Run with coverage (if pytest-cov installed)
make test-full
```

## Docker Testing

The project includes comprehensive Docker testing capabilities:

### Basic Docker Testing
```bash
# Build and run tests in containers
make build
make test-docker
```

### Full Docker Test Suite
```bash
# Run the dedicated test service with coverage
docker-compose up --build test

# Run specific test types
docker-compose run --rm test pytest tests/unit/ -v
docker-compose run --rm test pytest tests/integration/ -v
```

### Docker Test Environment
The Docker test setup includes:
- **Isolated test database**: Uses `koel_test` database
- **Separate Redis instance**: Uses Redis DB 1 for tests
- **Complete test coverage**: Runs pytest with coverage reporting
- **Health checks**: Ensures services are ready before running tests

## Test Structure

```
tests/
├── conftest.py              # Test fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_config.py       # Configuration tests
│   ├── test_cache_manager.py # Cache manager tests
│   ├── test_currency_controller.py # Currency controller tests
│   └── test_exchange_rate_controller.py # Exchange rate controller tests
└── integration/             # Integration tests
    └── test_api_routes_simple.py # API endpoint logic tests
```

## Test Features

- **In-memory SQLite database** for fast, isolated tests
- **Mock Redis client** for cache testing without external dependencies
- **Pydantic v1/v2 compatibility** for different environments
- **Comprehensive error handling** testing
- **API endpoint logic** testing without requiring FastAPI TestClient

## Troubleshooting

### "Module not found" errors
Ensure you're running tests from the project root directory.

### Database errors
Tests use in-memory SQLite, so no external database is required.

### Redis connection errors
Tests mock Redis operations, so no Redis server is required.

### Pydantic compatibility issues
The codebase supports both Pydantic v1 and v2 automatically.

## Adding New Tests

1. **Unit tests**: Add to `tests/unit/` for testing individual components
2. **Integration tests**: Add to `tests/integration/` for testing component interactions
3. **Use fixtures**: Leverage existing fixtures in `conftest.py` for database and mocking

Example:
```python
import pytest

@pytest.mark.unit
def test_my_function(test_db, mock_cache_manager):
    # Your test code here
    pass
```