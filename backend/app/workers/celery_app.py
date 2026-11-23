from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "subscription_auditor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Local-dev: run tasks inline in the calling process (no Redis/worker).
    task_always_eager=settings.celery_eager,
    task_eager_propagates=True,
)

# Nightly renewal/trial/price-hike scan at 03:00 UTC, and a weekly digest on
# Monday at 08:00 UTC.
celery_app.conf.beat_schedule = {
    "scan-renewals-nightly": {
        "task": "app.workers.tasks.scan_renewals",
        "schedule": crontab(hour=3, minute=0),
    },
    "weekly-digest": {
        "task": "app.workers.tasks.weekly_digest",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
}
