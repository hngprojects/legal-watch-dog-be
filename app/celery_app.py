import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import redis  # noqa: E402
from celery import Celery  # noqa: E402
from kombu import Exchange, Queue  # noqa: E402

from app.api.core.config import settings  # noqa: E402

# ✅ Initialize Celery app
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

# ✅ Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # ✅ Task discovery - ensure scraping tasks are loaded
    imports=[
        "app.api.modules.v1.scraping.service.tasks",
        "app.api.modules.v1.notifications.service.revision_notification_task",
    ],
)

# ✅ Queue configuration
celery_app.conf.task_queues = [
    Queue(
        "celery",
        Exchange("celery"),
        routing_key="celery",
    ),
    Queue(
        "scraping",
        Exchange("scraping"),
        routing_key="scraping.#",
    ),
]

# ✅ Default queue
celery_app.conf.task_default_queue = "celery"
celery_app.conf.task_default_exchange = "celery"
celery_app.conf.task_default_routing_key = "celery"

# ✅ Redis client for distributed locks
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)

# ✅ Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    "dispatch-due-sources-every-minute": {
        "task": "app.api.modules.v1.scraping.service.tasks.dispatch_due_sources",
        "schedule": 60.0,  # Every 60 seconds
        "options": {"queue": "celery"},
    },
    # Expire trials - runs every hour
    "expire-trials": {
        "task": "billing.tasks.expire_trials",
        "schedule": 3600.0,  # Every hour (3600 seconds)
    },
    # Update billing status - runs every 6 hours
    "update-billing-status": {
        "task": "billing.tasks.update_billing_status",
        "schedule": 21600.0,  # Every 6 hours (21600 seconds)
    },
    # Send trial reminders - runs daily at 9 AM UTC
    "send-trial-reminders": {
        "task": "billing.tasks.send_trial_reminders",
        "schedule": 86400.0,  # Daily (86400 seconds)
    },
}

celery_app.conf.timezone = "UTC"
