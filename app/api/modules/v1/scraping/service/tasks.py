"""
Celery tasks for web scraping operations.

This module handles:
- Periodic dispatching of due sources for scraping
- Individual source scraping operations
- Proper async/Celery integration without event loop conflicts
- Exponential backoff retry logic with jitter
- Dead Letter Queue (DLQ) for failed tasks
- Circuit breaker to prevent infinite retry loops
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from celery import shared_task
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.core.config import settings
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source
from app.celery_app import redis_client

logger = logging.getLogger(__name__)

# Define DLQ constants
CELERY_DLQ_KEY = "celery:scraping_dlq"

# ============================================================================
# Database Engine Management (CRITICAL FIX)
# ============================================================================

def create_celery_engine():
    """
    Create a NEW async database engine for Celery tasks.
    
    IMPORTANT: This creates a fresh engine for each task execution to avoid
    event loop conflicts. The engine is disposed at the end of the task.
    """
    logger.debug("Creating fresh Celery database engine")
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=2,  # Small pool since each task gets its own engine
        max_overflow=5,
        pool_recycle=3600,
    )


# ============================================================================
# Helper: Run Async Code in Celery Worker (THE KEY FIX)
# ============================================================================

def run_async_in_celery(coro):
    """
    Run async coroutine in Celery worker context.
    
    This CRITICAL function solves the event loop problem by:
    1. Creating a NEW event loop for EACH task execution
    2. Ensuring the loop is CLOSED after execution
    3. Preventing connection reuse across different loops
    
    Args:
        coro: Async coroutine to execute
        
    Returns:
        Result of the coroutine execution
    """
    # Create a fresh event loop for this task execution
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run the coroutine in the new loop
        return loop.run_until_complete(coro)
    finally:
        # CRITICAL: Clean up the loop after execution
        try:
            # Cancel any pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Wait for tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
            # Shutdown async generators
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            # Close the loop
            loop.close()
            # Clear the event loop reference
            asyncio.set_event_loop(None)


# ============================================================================
# Helper Functions
# ============================================================================

def get_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
    """Calculates the next scrape time based on frequency.

    Args:
        current_time: The current time from which to calculate the next scrape.
        frequency: The scraping frequency enum.

    Returns:
        The calculated next scrape time.
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
    """Circuit breaker to prevent infinite retry loops.

    CRITICAL SAFETY MECHANISM: If a source fails max_retries, we MUST push its
    next_scrape_time forward. Otherwise, the dispatcher will see it as 'due'
    immediately and infinite-loop it.

    Args:
        source_id: The UUID of the source that failed.
        error_msg: The error message to store in the database.
    """
    # Create fresh engine for this operation
    engine = create_celery_engine()
    
    try:
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as db:
            # Push 6 hours into the future to stop the bleeding
            backoff_time = datetime.now(timezone.utc) + timedelta(hours=6)

            logger.warning(
                f"Source {source_id} exhausted retries. "
                f"Pushing schedule to {backoff_time.isoformat()}"
            )

            stmt = (
                update(Source)
                .where(Source.id == source_id)
                .values(next_scrape_time=backoff_time, last_error=error_msg)
            )
            await db.execute(stmt)
            await db.commit()
    finally:
        await engine.dispose()


# ============================================================================
# Async Helper Functions
# ============================================================================

async def _dispatch_due_sources_async() -> str:
    """
    Async implementation of dispatching due sources.
    
    Returns:
        str: Summary message of dispatch results
    """
    # Acquire distributed lock
    lock_key = "celery:dispatch_due_sources:lock"
    lock_timeout = 300  # 5 minutes
    
    lock_acquired = redis_client.set(
        lock_key,
        value="locked",
        ex=lock_timeout,
        nx=True,
    )
    
    if not lock_acquired:
        logger.info("Dispatch due sources task is already running. Skipping.")
        return "Skipped: Another dispatch task is already running."
    
    logger.info("Acquired dispatch lock. Checking for due sources...")
    
    # Create fresh engine for this task execution
    engine = create_celery_engine()
    
    try:
        # Create session factory and session
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as db:
            now = datetime.now(timezone.utc)
            
            # Query for due sources
            query = (
                select(Source)
                .where(
                    (Source.next_scrape_time <= now) |
                    (Source.next_scrape_time.is_(None))
                )
                .where(Source.is_active.is_(True))
                .where(Source.is_deleted.is_(False))
                .order_by(Source.next_scrape_time, Source.id)
                .limit(1000)
            )
            
            result = await db.execute(query)
            due_sources = result.scalars().all()
            
            logger.info(f"Found {len(due_sources)} sources due for scraping")
            
            # Dispatch scraping tasks
            dispatched = 0
            failed = 0
            
            for source in due_sources:
                try:
                    scrape_source.apply_async(
                        args=[str(source.id)],
                        queue="scraping",
                    )
                    dispatched += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to dispatch source {source.id}: {e}")
            
            summary = f"Dispatched {dispatched} sources for scraping. Failed: {failed}"
            logger.info(summary)
            return summary
    
    finally:
        # Dispose the engine to close all connections properly
        await engine.dispose()
        
        # Always release the lock
        try:
            redis_client.delete(lock_key)
            logger.debug("Released dispatch lock")
        except Exception as e:
            logger.error(f"Failed to release dispatch lock: {e}")


async def _scrape_source_async(source_id: str) -> str:
    """Async implementation of source scraping with frequency scheduling.

    Fetches the source from the database, performs the actual scraping operation
    using ScraperService, and updates the source's next_scrape_time, last_scraped_at,
    and last_error based on the scraping results.

    Args:
        source_id: The UUID of the source to scrape.

    Returns:
        A message indicating the outcome of the scraping attempt.

    Raises:
        Exception: Re-raises exceptions from the scraping pipeline for retry handling.
    """
    from app.api.modules.v1.scraping.service.scraper_service import ScraperService

    # Create fresh engine for this task execution
    engine = create_celery_engine()
    
    try:
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as db:
            logger.info(f"Running _scrape_source_async for source {source_id}")
            
            query = select(Source).where(Source.id == UUID(source_id))
            result = await db.execute(query)
            source = result.scalars().first()

            if not source:
                logger.warning(f"Source with ID {source_id} not found.")
                return f"Source {source_id} not found."

            logger.info(f"Attempting to scrape source: {source.name} (ID: {source.id})")

            try:
                scraper_service = ScraperService(db)
                scrape_result = await scraper_service.execute_scrape_job(str(source.id))

                # Calculate next scrape time based on frequency
                new_next_scrape_time = get_next_scrape_time(
                    datetime.now(timezone.utc), source.scrape_frequency
                )
                source.next_scrape_time = new_next_scrape_time
                source.last_scraped_at = datetime.now(timezone.utc)
                source.last_error = None  # Clear previous errors

                db.add(source)
                await db.commit()
                await db.refresh(source)

                change_detected = scrape_result.get("change_detected")
                change_status = "with changes" if change_detected else "no changes"
                logger.info(
                    f"Successfully scraped source {source.name} ({change_status}). "
                    f"Next scrape time: {source.next_scrape_time}"
                )
                return (
                    f"Source {source.id} scraped successfully ({change_status}). "
                    f"Next scrape: {source.next_scrape_time}"
                )

            except Exception as e:
                error_msg = f"Scraping failed: {str(e)}"
                logger.error(f"Error scraping source {source.name}: {error_msg}")

                # Update last_error but don't update next_scrape_time yet
                source.last_error = error_msg
                db.add(source)
                await db.commit()

                # Re-raise to trigger Celery retry mechanism
                raise
    finally:
        # Dispose the engine to close all connections properly
        await engine.dispose()


# ============================================================================
# Celery Tasks
# ============================================================================

@shared_task(bind=True, max_retries=settings.SCRAPE_MAX_RETRIES)
def scrape_source(self, source_id: str):
    """Performs the scraping of a single source with exponential backoff and jitter.

    This task attempts to scrape a given source. If it fails, it retries with
    an exponential backoff strategy, including jitter to prevent thundering herds.
    Upon successful completion, it atomically updates the source's next_scrape_time.
    After max retries, the task is moved to the Dead Letter Queue (DLQ) and the
    circuit breaker is triggered to prevent infinite loops.

    Args:
        self: The Celery task instance.
        source_id: The UUID of the source to be scraped.

    Returns:
        A message indicating the outcome of the scraping attempt.
    """
    try:
        # ✅ THE FIX: Use our helper function instead of asyncio.run()
        return run_async_in_celery(_scrape_source_async(source_id))
    except Exception as exc:
        retry_count = self.request.retries
        # Smart Exponential Backoff: 2s, 4s, 8s, 16s...
        delay = min(settings.SCRAPE_MAX_DELAY, settings.SCRAPE_BASE_DELAY * (2**retry_count))
        jitter = random.uniform(0, delay * 0.1)
        countdown = delay + jitter

        if retry_count < settings.SCRAPE_MAX_RETRIES:
            logger.warning(
                f"Scrape failed for {source_id}. Retrying in {countdown:.2f} seconds. Error: {exc}"
            )
            raise self.retry(exc=exc, countdown=countdown)
        else:
            # Max retries exhausted, move to DLQ
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

            # Update DB to prevent immediate re-dispatch (Infinite Loop Fix)
            try:
                run_async_in_celery(_handle_scrape_failure_async(source_id, error_msg))
            except Exception as db_exc:
                logger.error(f"CRITICAL: Failed to update source schedule after failure: {db_exc}")

            logger.error(
                f"Scrape source {source_id} failed after {settings.SCRAPE_MAX_RETRIES} retries. "
                f"Task {self.request.id} moved to DLQ."
            )
            return f"Failed: Source {source_id} moved to DLQ."


@shared_task(bind=True)
def dispatch_due_sources(self):
    """Dispatches scraping tasks for sources whose next_scrape_time has passed.

    This Celery Beat task runs periodically. It uses a distributed lock to ensure
    that only one instance of the task runs at a time across all workers.
    It queries for due sources and dispatches individual scrape_source tasks.

    Args:
        self: The Celery task instance.

    Returns:
        A message indicating the outcome (dispatched, or skipped due to lock).

    Raises:
        redis.RedisError: If there's a Redis connection failure.
    """
    logger.info("Dispatch task triggered")
    
    try:
        # ✅ THE FIX: Use our helper function instead of asyncio.run()
        result = run_async_in_celery(_dispatch_due_sources_async())
        return result
    
    except Exception as e:
        logger.error("Error in dispatch_due_sources task", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# Export tasks
__all__ = [
    "dispatch_due_sources",
    "scrape_source",
]
