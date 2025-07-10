.PHONY: help build up down test test-unit test-integration clean logs shell

# Default target
help:
	@echo "Available targets:"
	@echo "  build           - Build Docker containers"
	@echo "  up              - Start all services"
	@echo "  down            - Stop all services"
	@echo "  test-basic      - Run basic tests (no dependencies)"
	@echo "  test            - Run all available tests"
	@echo "  test-full       - Run pytest with coverage"
	@echo "  test-unit       - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-docker     - Run tests in Docker"
	@echo "  clean           - Clean up Docker containers and volumes"
	@echo "  logs            - Show logs from all services"
	@echo "  shell           - Open shell in API container"
	@echo "  lint            - Run code linting"
	@echo "  format          - Format code"

# Build Docker containers
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d postgres redis
	sleep 10
	docker-compose run --rm init
	docker-compose up -d api celery_worker celery_beat

# Stop all services
down:
	docker-compose down

# Run basic tests (no dependencies required)
test-basic:
	python test_local.py

# Run all tests locally (requires pytest)
test:
	python run_tests.py

# Run pytest-based tests with coverage (requires pytest + coverage)
test-full:
	pytest -v --cov=app --cov-report=term-missing --cov-report=html

# Run unit tests only
test-unit:
	pytest tests/unit/ -v

# Run integration tests only
test-integration:
	pytest tests/integration/ -v

# Run tests in Docker
test-docker:
	docker-compose run --rm test

# Clean up Docker containers and volumes
clean:
	docker-compose down -v
	docker system prune -f

# Show logs from all services
logs:
	docker-compose logs -f

# Open shell in API container
shell:
	docker-compose exec api bash

# Run code linting (if tools are available)
lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check app/ tests/; \
	elif command -v flake8 >/dev/null 2>&1; then \
		flake8 app/ tests/; \
	else \
		echo "No linting tool found. Install ruff or flake8."; \
	fi

# Format code (if tools are available)
format:
	@if command -v black >/dev/null 2>&1; then \
		black app/ tests/; \
	else \
		echo "Black not found. Install black for code formatting."; \
	fi

# Install dependencies
install:
	pip install -r requirements.txt

# Run development server
dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload