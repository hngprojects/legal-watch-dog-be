"""Celery tasks for the scraping module.

This module defines the synchronous tasks for scraping data sources,
including a periodic task to dispatch scrapers and the individual scraper task
with retry logic and circuit breaking.
"""

import asyncio
import json
import random
from datetime import datetime, timedelta, timezone

import redis
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlmodel import select, update

from app.api.core.config import settings
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source

logger = get_task_logger(__name__)

redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

DISPATCH_LOCK_KEY = "celery:dispatch_due_sources_lock"
CELERY_DLQ_KEY = "celery:scraping_dlq"


def get_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
    """Calculates the next scrape time based on frequency.

    Args:
        current_time (datetime): The current time anchor.
        frequency (ScrapeFrequency): The frequency enum (DAILY, WEEKLY, etc.).

    Returns:
        datetime: The calculated next execution time.
    """
    frequency_map = {
        ScrapeFrequency.DAILY: timedelta(days=1),
        ScrapeFrequency.WEEKLY: timedelta(weeks=1),
        ScrapeFrequency.MONTHLY: timedelta(days=30),
        ScrapeFrequency.HOURLY: timedelta(hours=1),
    }
    delta = frequency_map.get(frequency, timedelta(days=1))
    return current_time + delta


async def _handle_scrape_failure_async(source_id: str, error_msg: str):
    """Updates the source schedule on failure to prevent infinite retry loops.

    Args:
        source_id (str): The UUID of the source that failed.
        error_msg (str): The error message to persist.
    """
    async with AsyncSessionLocal() as db:
        backoff_time = datetime.now(timezone.utc) + timedelta(hours=6)

        logger.warning(f"Source {source_id} exhausted retries. Pushing schedule to {backoff_time}")

        stmt = (
            update(Source)
            .where(Source.id == source_id)
            .values(next_scrape_time=backoff_time, last_error=error_msg)
        )
        await db.exec(stmt)
        await db.commit()


async def _scrape_source_async(source_id: str) -> str:
    """Async logic to initialize the service and execute the scrape pipeline.

    Args:
        source_id (str): The UUID of the target source.

    Returns:
        str: A status message describing the outcome.

    Raises:
        Exception: If the pipeline fails, re-raised for Celery retry.
    """
    from app.api.modules.v1.scraping.service.scraper_service import ScraperService

    logger.info(f"Running scrape for source {source_id}")

    async with AsyncSessionLocal() as db:
        query = select(Source).where(Source.id == source_id)
        result = await db.execute(query)
        source = result.scalars().first()

        if not source:
            logger.warning(f"Source {source_id} not found.")
            return f"Source {source_id} not found."

        try:
            scraper_service = ScraperService(db)
            scrape_result = await scraper_service.execute_scrape_job(str(source.id))

            new_next_scrape_time = get_next_scrape_time(
                datetime.now(timezone.utc), source.scrape_frequency
            )
            source.next_scrape_time = new_next_scrape_time
            source.last_scraped_at = datetime.now(timezone.utc)
            source.last_error = None

            db.add(source)
            await db.commit()
            await db.refresh(source)

            change_status = "with changes" if scrape_result.get("change_detected") else "no changes"
            msg = (
                f"Source {source.id} scraped successfully ({change_status}). "
                f"Next: {source.next_scrape_time}"
            )
            logger.info(msg)
            return msg

        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            logger.error(f"Error scraping source {source.name}: {error_msg}")

            source.last_error = error_msg
            db.add(source)
            await db.commit()
            raise


@shared_task(bind=True, max_retries=settings.SCRAPE_MAX_RETRIES)
def scrape_source(self, source_id: str):
    """Celery worker task to scrape a single source.

    Executes the async scraping logic synchronously. Handles exponential backoff
    retries and dead-letter queueing upon exhaustion.

    Args:
        source_id (str): The UUID of the source.

    Returns:
        str: Success or Failure message.
    """
    try:
        return asyncio.run(_scrape_source_async(source_id))
    except Exception as exc:
        redis_client = redis.Redis(connection_pool=redis_pool)

        retry_count = self.request.retries
        delay = min(settings.SCRAPE_MAX_DELAY, settings.SCRAPE_BASE_DELAY * (2**retry_count))
        jitter = random.uniform(0, delay * 0.1)
        countdown = delay + jitter

        if retry_count < settings.SCRAPE_MAX_RETRIES:
            logger.warning(f"Scrape failed for {source_id}. Retrying in {countdown:.2f}s.")
            raise self.retry(exc=exc, countdown=countdown)
        else:
            error_msg = str(exc)
            dlq_entry = {
                "task_id": self.request.id,
                "source_id": source_id,
                "error_message": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "args": self.request.args,
                "kwargs": self.request.kwargs,
            }
            redis_client.lpush(CELERY_DLQ_KEY, json.dumps(dlq_entry))

            try:
                asyncio.run(_handle_scrape_failure_async(source_id, error_msg))
            except Exception as db_exc:
                logger.error(f"CRITICAL: Failed to update schedule after failure: {db_exc}")

            return f"Failed: Source {source_id} moved to DLQ."


async def _dispatch_due_sources_async(app) -> int:
    """Async logic to query due sources and dispatch tasks.

    Args:
        app: The Celery application instance.

    Returns:
        int: Total number of sources dispatched.
    """
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        total_dispatched = 0
        batch_size = settings.SCRAPE_BATCH_SIZE

        while True:
            query = (
                select(Source)
                .where((Source.next_scrape_time <= now) | (Source.next_scrape_time.is_(None)))
                .order_by(Source.next_scrape_time, Source.id)
                .limit(batch_size)
            )
            result = await db.execute(query)
            due_sources = result.scalars().all()

            if not due_sources:
                break

            for src in due_sources:
                in_progress_time = get_next_scrape_time(now, src.scrape_frequency)
                src.next_scrape_time = in_progress_time

                db.add(src)
                await db.commit()

                app.send_task(
                    "app.api.modules.v1.scraping.service.tasks.scrape_source",
                    args=[str(src.id)],
                )

                total_dispatched += 1

            logger.info(f"Dispatched batch of {len(due_sources)} sources.")

        return total_dispatched


@shared_task(bind=True)
def dispatch_due_sources(self):
    """Celery Beat task to schedule scraping jobs.

    Uses a distributed Redis lock to prevent overlapping runs.

    Returns:
        str: Summary of dispatch action.
    """
    redis_client = redis.Redis(connection_pool=redis_pool)

    try:
        lock_acquired = redis_client.set(
            DISPATCH_LOCK_KEY, "locked", nx=True, ex=settings.SCRAPE_DISPATCH_LOCK_TIMEOUT
        )

        if not lock_acquired:
            return "Skipped: Dispatch task locked."

        total_dispatched = asyncio.run(_dispatch_due_sources_async(self.app))
        return f"Dispatched {total_dispatched} sources."

    except redis.RedisError as e:
        logger.error(f"Redis error: {e}", exc_info=True)
        return "Aborted: Redis failure."
