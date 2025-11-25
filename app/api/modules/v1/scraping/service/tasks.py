"""
Celery tasks for the scraping module.

This module defines the synchronous tasks for
scraping data sources,
including a periodic task to dispatch scrapers and
the individual scraper task
with retry logic.
"""

import asyncio
import json
import random
from datetime import datetime, timedelta, timezone

import redis
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlmodel import select

from app.api.core.config import settings
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source

logger = get_task_logger(__name__)

# Initialize Redis Connection Pool
redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

# Define lock constants
DISPATCH_LOCK_KEY = "celery:dispatch_due_sources_lock"

# Define DLQ constants
CELERY_DLQ_KEY = "celery:scraping_dlq"


def get_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
    """Calculates the next scrape time based on frequency.

    Args:
        current_time (datetime): The current time from which to calculate the next scrape.
        frequency (ScrapeFrequency): The scraping frequency enum.

    Returns:
        datetime: The calculated next scrape time.
    """
    frequency_map = {
        ScrapeFrequency.DAILY: timedelta(days=1),
        ScrapeFrequency.WEEKLY: timedelta(weeks=1),
        ScrapeFrequency.MONTHLY: timedelta(days=30),
        ScrapeFrequency.HOURLY: timedelta(hours=1),
    }
    delta = frequency_map.get(frequency, timedelta(days=1))
    return current_time + delta


async def _scrape_source_async(source_id: str):
    """Async implementation of the scraping logic."""
    logger.info(f"Running _scrape_source_async for source {source_id} in async loop.")
    async with AsyncSessionLocal() as db:
        query = select(Source).where(Source.id == source_id)
        result = await db.execute(query)
        source = result.scalars().first()

        if not source:
            logger.warning(f"Source with ID {source_id} not found.")
            return f"Source {source_id} not found."

        logger.info(f"Attempting to scrape source: {source.name} (ID: {source.id})")

        # Simulate async work (to be replaced with actual async scraping logic later)
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # If scraping is successful
        new_next_scrape_time = get_next_scrape_time(
            datetime.now(timezone.utc), source.scrape_frequency
        )
        source.next_scrape_time = new_next_scrape_time
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            f"Successfully scraped source {source.name}. "
            f"Next scrape time: {source.next_scrape_time}"
        )
        return f"Source {source.id} scraped successfully. Next scrape: {source.next_scrape_time}"


@shared_task(bind=True, max_retries=settings.SCRAPE_MAX_RETRIES)
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
        # Run the async implementation synchronously
        return asyncio.run(_scrape_source_async(source_id))
    except Exception as exc:
        # Use the connection pool
        redis_client = redis.Redis(connection_pool=redis_pool)

        retry_count = self.request.retries
        # Use dynamic settings
        delay = min(settings.SCRAPE_MAX_DELAY, settings.SCRAPE_BASE_DELAY * (2**retry_count))
        jitter = random.uniform(0, delay * 0.1)
        countdown = delay + jitter

        if retry_count < settings.SCRAPE_MAX_RETRIES:
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
                f"Scraping source {source_id} failed after {settings.SCRAPE_MAX_RETRIES} retries."
                f"Task {self.request.id} moved to DLQ."
            )
            return f"Failed: Source {source_id} moved to DLQ."


async def _dispatch_due_sources_async(app):
    """Async implementation of the dispatch logic."""
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Base query for due sources
        query = select(Source).where(
            (Source.next_scrape_time <= now) | (Source.next_scrape_time.is_(None))
        )

        total_dispatched = 0
        offset = 0
        batch_size = settings.SCRAPE_BATCH_SIZE

        while True:
            # Fetch in batches
            batch_query = query.offset(offset).limit(batch_size)
            result = await db.execute(batch_query)
            due_sources = result.scalars().all()

            if not due_sources:
                break

            for src in due_sources:
                app.send_task(
                    "app.api.modules.v1.scraping.service.tasks.scrape_source",
                    args=[str(src.id)],
                )

            count = len(due_sources)
            total_dispatched += count
            offset += count

            logger.info(f"Dispatched batch of {count} sources.")

        return total_dispatched


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
    # Use the connection pool
    redis_client = redis.Redis(connection_pool=redis_pool)

    try:
        lock_acquired = redis_client.set(
            DISPATCH_LOCK_KEY, "locked", nx=True, ex=settings.SCRAPE_DISPATCH_LOCK_TIMEOUT
        )

        if not lock_acquired:
            logger.info("Dispatch due sources task is already running. Skipping.")
            return "Skipped: Another dispatch task is already running."

        logger.info("Acquired dispatch lock. Checking for due sources...")

        # Run the async implementation synchronously
        total_dispatched = asyncio.run(_dispatch_due_sources_async(self.app))

        if total_dispatched == 0:
            logger.info("No sources are due for scraping.")
            return "No sources to dispatch."

        logger.info(f"Dispatched total {total_dispatched} sources for scraping.")
        return f"Dispatched {total_dispatched} sources"

    except redis.RedisError as e:
        logger.error(f"Redis error in dispatch_due_sources: {e}", exc_info=True)
        return "Aborted: Redis connection failed."
