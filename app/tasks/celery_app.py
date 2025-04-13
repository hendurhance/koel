from celery import Celery
from celery.schedules import crontab
from app.core.config import config

celery_app = Celery(
    "exchange_rate_tasks",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
)

celery_app.conf.task_routes = {"app.tasks.*": {"queue": "exchange_rate_queue"}}

# Schedule different scraping intervals for different currency groups
celery_app.conf.beat_schedule = {
    # Primary currencies every 6 hours
    "scrape-primary-currencies-every-6-hours": {
        "task": "app.tasks.exchange_rates.scrape_currency_group",
        "schedule": crontab(hour="0,6,12,18", minute=0),
        "args": ["primary"],
    },
    
    # Secondary currencies every 12 hours
    "scrape-secondary-currencies-every-12-hours": {
        "task": "app.tasks.exchange_rates.scrape_currency_group",
        "schedule": crontab(hour="3,15", minute=0),
        "args": ["secondary"],
    },
    # Optionally, if you still want an overall full scrape at a time when group tasks are not running,
    # schedule it at an off-peak hour. Otherwise, you can remove it.
    # "scrape-all-currencies-daily": {
    #     "task": "app.tasks.exchange_rates.scrape_all_exchange_rates",
    #     "schedule": crontab(hour="21", minute="0"),
    # },
    # Clean up old task records weekly
    "cleanup-old-task-records": {
        "task": "app.tasks.maintenance.cleanup_old_task_records",
        "schedule": crontab(day_of_week="sunday", hour="3", minute="0"),
    },
    "create-next-month-partition": {
        "task": "app.tasks.maintenance.create_next_month_partition",
        "schedule": crontab(day_of_month="28-31", hour="0", minute="0"),
    },
}

from app.tasks.exchange_rates import scrape_currency_group, scrape_all_exchange_rates, scrape_single_currency
from app.tasks.maintenance import cleanup_old_task_records, create_next_month_partition