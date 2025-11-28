from celery import Celery
from celery.schedules import crontab

from app.api.core.config import settings
from app.api.modules.v1.scraping.service.tasks import dispatch_due_sources

celery_app = Celery(
    "legal_watch_dog",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.api.modules.v1.scraping.service.tasks",
        "app.api.modules.v1.notifications.service.revision_notification_task",
    ],
)

celery_app.conf.beat_schedule = {
    "dispatch-due-sources-every-minute": {
        "task": dispatch_due_sources.name,
        "schedule": crontab(minute="*"),
        "args": (),
    },
    # Expire trials - runs every hour
    "expire-trials": {
        "task": "billing.tasks.expire_trials",
        "schedule": crontab(minute=0),
    },
    # Send trial reminders - runs daily at 9 AM
    "send-trial-reminders": {
        "task": "billing.tasks.send_trial_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
}

celery_app.conf.timezone = "UTC"
