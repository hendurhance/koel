from celery import Celery
from celery.schedules import crontab

from koel.config import get_settings
from koel.observability.logging import configure_logging

settings = get_settings()
configure_logging()

celery_app = Celery(
    "koel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "koel.tasks.scrape",
        "koel.tasks.maintenance",
        "koel.tasks.notify",
        "koel.tasks.usage",
        "koel.tasks.backup",
    ],
)

celery_app.conf.update(
    task_default_queue="scraping",
    task_routes={
        "koel.tasks.scrape.*": {"queue": "scraping"},
        "koel.tasks.notify.*": {"queue": "notifications"},
        "koel.tasks.backup.*": {"queue": "maintenance"},
        "koel.tasks.maintenance.*": {"queue": "maintenance"},
        "koel.tasks.usage.*": {"queue": "usage"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "scrape-dispatch-cycle": {
        "task": "koel.tasks.scrape.dispatch_cycle",
        "schedule": 60.0,
    },
    "materialize-cross-rates": {
        # Runs after dispatch (on average) so newly-written USD rates are picked up.
        "task": "koel.tasks.scrape.materialize_cross_rates_cycle",
        "schedule": 120.0,
    },
    "partitions-ensure": {
        "task": "koel.tasks.maintenance.ensure_partitions",
        "schedule": crontab(hour="2", minute="0"),
    },
    "partitions-drop-expired": {
        "task": "koel.tasks.maintenance.drop_old_partitions",
        "schedule": crontab(hour="3", minute="0"),
    },
    "usage-flush-events": {
        # Drain the usage stream every 30s — small enough that a crash loses
        # at most the in-flight batch; large enough that the flusher isn't
        # competing with live traffic for DB connections.
        "task": "koel.tasks.usage.flush_usage_events",
        "schedule": 30.0,
    },
    "backup-daily": {
        # 04:00 UTC: after most regions' business hours, long before any
        # daily scrape-heavy window on the other side of the planet.
        "task": "koel.tasks.backup.daily_backup",
        "schedule": crontab(hour="4", minute="0"),
    },
}
