api: uv run uvicorn koel.api.main:app --reload --host 0.0.0.0 --port 8000
worker: uv run celery -A koel.tasks.celery_app worker --loglevel=info --queues=scraping,notifications,maintenance,usage
beat: uv run celery -A koel.tasks.celery_app beat --loglevel=info
