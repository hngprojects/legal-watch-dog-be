"""
Celery tasks for the scraping module.

This module defines the synchronous tasks for
scraping data sources,
including a periodic task to dispatch scrapers and
the individual scraper task
with retry logic.
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone

import redis
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlmodel import Session, select

from app.api.core.config import settings
from app.api.db.database import engine
from app.api.modules.v1.scraping.models.source_model import Source

logger = get_task_logger(__name__)

# Define retry settings for exponential backoff with jitter
MAX_RETRIES = 5
BASE_DELAY = 60  # seconds
MAX_DELAY = 3600  # seconds (1 hour)

# Define lock constants
DISPATCH_LOCK_KEY = "celery:dispatch_due_sources_lock"
LOCK_TIMEOUT_SECONDS = 60  # 1 minute

# Define DLQ constants
CELERY_DLQ_KEY = "celery:scraping_dlq"


def get_next_scrape_time(current_time: datetime, frequency: str) -> datetime:
    """Calculates the next scrape time based on frequency.

    Args:
        current_time (datetime): The current time from which to calculate the next scrape.
        frequency (str): The scraping frequency (e.g., "DAILY", "WEEKLY", "MONTHLY", "HOURLY").

    Returns:
        datetime: The calculated next scrape time.
    """
    frequency_map = {
        "DAILY": timedelta(days=1),
        "WEEKLY": timedelta(weeks=1),
        "MONTHLY": timedelta(days=30),  # Approximation for monthly
        "HOURLY": timedelta(hours=1),
    }
    delta = frequency_map.get(frequency.upper(), timedelta(days=1))  # Default to daily
    return current_time + delta


@shared_task(bind=True, max_retries=MAX_RETRIES)
def scrape_source(self, source_id: str):
    """Performs the scraping of a single source with exponential backoff and jitter.

    This task attempts to scrape a given source. If it fails, it retries with
    an exponential backoff strategy, including jitter to prevent thundering herds.
    Upon successful completion, it atomically updates the source's next_scrape_time.

    Args:
        self: The Celery task instance.
        source_id (str): The UUID of the source to be scraped.

    Returns:
        str: A message indicating the outcome of the scraping attempt.
    """
    try:
        with Session(engine) as db:
            query = select(Source).where(Source.id == source_id)
            result = db.exec(query)
            source = result.first()

            if not source:
                logger.warning(f"Source with ID {source_id} not found.")
                return f"Source {source_id} not found."

            logger.info(f"Attempting to scrape source: {source.name} (ID: {source.id})")

            time.sleep(random.uniform(0.1, 0.5))

            # If scraping is successful
            new_next_scrape_time = get_next_scrape_time(
                datetime.now(timezone.utc), source.scrape_frequency
            )
            source.next_scrape_time = new_next_scrape_time
            db.add(source)
            db.commit()
            db.refresh(source)

            logger.info(
                f"Successfully scraped source {source.name}. "
                f"Next scrape time: {source.next_scrape_time}"
            )
            return (
                f"Source {source.id} scraped successfully. Next scrape: {source.next_scrape_time}"
            )
    except Exception as exc:
        redis_client = None
        try:
            redis_client = redis.Redis.from_url(settings.REDIS_URL, db=0, decode_responses=True)

            retry_count = self.request.retries
            delay = min(MAX_DELAY, BASE_DELAY * (2**retry_count))
            jitter = random.uniform(0, delay * 0.1)
            countdown = delay + jitter

            if retry_count < MAX_RETRIES:
                logger.error(
                    f"Scraping for source {source_id} failed. Retrying in "
                    f"{countdown:.2f} seconds. Error: {exc}"
                )
                raise self.retry(exc=exc, countdown=countdown)
            else:
                # Max retries exhausted, move to DLQ
                dlq_entry = {
                    "task_id": self.request.id,
                    "source_id": source_id,
                    "error_message": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "args": self.request.args,
                    "kwargs": self.request.kwargs,
                }
                redis_client.lpush(CELERY_DLQ_KEY, json.dumps(dlq_entry))
                logger.error(
                    f"Scraping for source {source_id} failed after {MAX_RETRIES} retries. "
                    f"Task {self.request.id} moved to DLQ."
                )
                return f"Failed: Source {source_id} moved to DLQ."
        except redis.RedisError as redis_exc:
            logger.error(
                f"Redis error while handling failed task {self.request.id} "
                f"for source {source_id}: {redis_exc}",
                exc_info=True,
            )

            raise exc
        finally:
            if redis_client:
                try:
                    redis_client.close()
                except Exception:
                    pass


@shared_task(bind=True)
def dispatch_due_sources(self):
    """
    Dispatches scraping tasks for sources whose next_scrape_time has passed.

    This Celery Beat task runs periodically. It uses a distributed lock to ensure
    that only one instance of the task runs at a time across all workers.
    It queries for due sources and dispatches individual `scrape_source` tasks.

    Returns:
        str: A message indicating the outcome (dispatched, or skipped due to lock).
    """
    redis_client = None
    try:
        redis_client = redis.Redis.from_url(settings.REDIS_URL, db=0, decode_responses=True)

        lock_acquired = redis_client.set(
            DISPATCH_LOCK_KEY, "locked", nx=True, ex=LOCK_TIMEOUT_SECONDS
        )

        if not lock_acquired:
            logger.info("Dispatch due sources task is already running. Skipping.")
            return "Skipped: Another dispatch task is already running."

        logger.info("Acquired dispatch lock. Checking for due sources...")

        with Session(engine) as db:
            now = datetime.now(timezone.utc)

            query = select(Source).where(
                (Source.next_scrape_time <= now) | (Source.next_scrape_time.is_(None))
            )
            result = db.exec(query)
            due_sources = result.all()

            if not due_sources:
                logger.info("No sources are due for scraping.")
                return "No sources to dispatch."

            for src in due_sources:
                self.app.send_task(
                    "app.api.modules.v1.scraping.service.tasks.scrape_source",
                    args=[str(src.id)],
                )

            logger.info(f"Dispatched {len(due_sources)} sources for scraping.")
            return f"Dispatched {len(due_sources)} sources"

    except redis.RedisError as e:
        logger.error(f"Redis error in dispatch_due_sources: {e}", exc_info=True)
        return "Aborted: Redis connection failed."
    finally:
        if redis_client:
            try:
                redis_client.close()
            except Exception:
                pass
