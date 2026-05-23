.PHONY: help setup dev dev-api dev-worker dev-beat test test-unit test-integration \
        lint format typecheck db-reset uv-lock openapi \
        docker-build docker-up docker-down docker-dev docker-logs docker-shell docker-clean

SHELL := /bin/bash

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ----- Local dev (no Docker) -------------------------------------------------

setup:  ## Bootstrap local env (Postgres, Redis, uv, deps). Works on mac/linux.
	bash scripts/setup-local.sh

uv-lock:  ## Regenerate uv.lock from pyproject.toml
	uv lock

dev:  ## Run api + worker + beat together via honcho
	uv run honcho -f Procfile start

dev-api:  ## Run just the API (hot reload)
	uv run uvicorn koel.api.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:  ## Run just the Celery worker
	uv run celery -A koel.tasks.celery_app worker --loglevel=info \
	  --queues=scraping,notifications,maintenance,usage

dev-beat:  ## Run just Celery beat
	uv run celery -A koel.tasks.celery_app beat --loglevel=info

# ----- Quality ---------------------------------------------------------------

lint:  ## ruff check
	uv run ruff check koel tests

format:  ## ruff format
	uv run ruff format koel tests

typecheck:  ## mypy
	uv run mypy koel

# ----- Tests -----------------------------------------------------------------

test: test-unit  ## Alias: unit tests

test-unit:  ## Unit tests (fast, no external deps)
	uv run pytest tests/unit -v

test-integration:  ## Integration tests (requires live Postgres + Redis)
	uv run pytest tests/integration -v -m integration

load:  ## Run Phase-10 load test (requires KOEL_API_KEY and a running stack)
	KOEL_API_KEY=$${KOEL_API_KEY:?set KOEL_API_KEY to a valid key} \
	uv run --extra load locust -f tests/load/locustfile.py \
	  --host $${KOEL_HOST:-http://localhost:8000} \
	  --users $${USERS:-500} --spawn-rate $${SPAWN_RATE:-50} \
	  --run-time $${RUN_TIME:-5m} --headless \
	  --csv build/loadtest

# ----- Frontend API types ----------------------------------------------------

openapi:  ## Dump OpenAPI schema -> frontend/openapi.json, then regen frontend TS types
	uv run python scripts/dump_openapi.py
	cd frontend && npm run gen:types

# ----- Database --------------------------------------------------------------

db-reset:  ## Drop + recreate the dev database, then migrate + seed
	@echo "Resetting development database..."
	@psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS koel;" postgres
	@psql -h localhost -U postgres -c "CREATE DATABASE koel OWNER postgres;" postgres
	uv run alembic upgrade head
	uv run python -m koel.db.seed || echo "(seed script not yet implemented)"

# ----- Docker ----------------------------------------------------------------

docker-build:  ## Build the Docker image
	docker compose build

docker-up:  ## Start the full stack (prod-like)
	docker compose up -d

docker-dev:  ## Start with the dev override (bind mount + reload)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

docker-down:  ## Stop the stack
	docker compose down

docker-logs:  ## Tail logs from all services
	docker compose logs -f

docker-shell:  ## Open a shell inside the api container
	docker compose exec api bash

docker-clean:  ## Stop + delete volumes (destroys data!)
	docker compose down -v
