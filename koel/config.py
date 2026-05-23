from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core
    APP_ENV: Literal["development", "production"] = "development"
    APP_SECRET: str = Field(default="please-change-me")
    APP_BASE_URL: str = "http://localhost:8000"
    # Where magic-link emails should send the user. Falls back to APP_BASE_URL
    # for API-only deployments without a separate dashboard.
    FRONTEND_BASE_URL: str = ""
    LOG_LEVEL: str = "INFO"

    # Cookies
    SESSION_COOKIE_NAME: str = "koel_session"

    # Datastores
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/koel"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Connection pool, per process. Each API worker / Celery process opens its
    # own pool, so for safe horizontal scaling keep
    #   processes * (DB_POOL_SIZE + DB_MAX_OVERFLOW) <= postgres max_connections.
    # Defaults (5+5=10/process) leave headroom under a default max_connections
    # of 100; for real multi-worker scale, front Postgres with PgBouncer.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 10  # seconds to wait for a free conn before failing

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Scraping
    SCRAPE_INTERVAL_MAJOR: int = 300
    SCRAPE_INTERVAL_STANDARD: int = 3600
    SCRAPE_INTERVAL_EXOTIC: int = 21600
    SCRAPE_DELTA_THRESHOLD_BPS: int = 5
    SCRAPE_ANCHOR_INTERVAL_SECONDS: int = 3600
    PROXY_URL: str = ""

    # Auth / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@example.com"
    SMTP_TLS: bool = True
    MAGIC_LINK_TTL_SECONDS: int = 15 * 60
    SESSION_TTL_SECONDS: int = 7 * 24 * 3600
    INITIAL_ADMIN_EMAIL: str = ""

    # API keys
    API_KEYS_REQUIRED: bool = True
    DEFAULT_RATE_LIMIT_PER_MIN: int = 60
    KEY_TOUCH_THROTTLE_SECONDS: int = 60

    # Usage tracking (Redis stream → batched Postgres flush)
    USAGE_TRACKING_ENABLED: bool = True
    USAGE_STREAM_MAXLEN: int = 1_000_000
    USAGE_FLUSH_BATCH_SIZE: int = 5_000

    # Notifications
    SLACK_WEBHOOK_URL: str = ""
    # Crawl summaries are off by default — circuit alerts are usually enough
    # signal, and a per-cycle summary can be noisy on a small Slack workspace.
    SLACK_NOTIFY_ON_CRAWL: bool = False
    SLACK_NOTIFY_ON_CIRCUIT: bool = True

    # Backups
    BACKUP_ENABLED: bool = False
    BACKUP_S3_BUCKET: str = ""
    BACKUP_S3_PREFIX: str = "koel/backups"
    BACKUP_S3_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
