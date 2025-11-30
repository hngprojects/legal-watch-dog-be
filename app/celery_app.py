from celery import Celery
from celery.schedules import crontab

from app.api.core.config import settings

celery_app = Celery(
    "legal_watch_dog",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.api.modules.v1.scraping.service.tasks",
        "app.api.modules.v1.billing.tasks",
        "app.api.modules.v1.notifications.service.revision_notification_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)


celery_app.conf.beat_schedule = {
    "dispatch-due-sources-every-minute": {
        "task": "app.api.modules.v1.scraping.service.tasks.dispatch_due_sources",
        "schedule": crontab(minute="*"),
    },
    "expire-trials": {
        "task": "app.api.modules.v1.billing.tasks.expire_trials",
        "schedule": crontab(minute=0),
    },
    "update-billing-status": {
        "task": "app.api.modules.v1.billing.tasks.update_billing_status",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "send-trial-reminders": {
        "task": "app.api.modules.v1.billing.tasks.send_trial_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
}
