import json
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlmodel import Session, select


from app.api.core.config import settings
from app.api.db.database import engine
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source
from app.api.modules.v1.scraping.service.scraper_service import ScraperService

logger = get_task_logger(__name__)

# Define retry settings for exponential backoff with jitter
MAX_RETRIES = 5
BASE_DELAY = 60
MAX_DELAY = 3600

# Define lock constants
DISPATCH_LOCK_KEY = "celery:dispatch_due_sources_lock"
LOCK_TIMEOUT_SECONDS = 60
CELERY_DLQ_KEY = "celery:scraping_dlq"
DOMAIN_RATE_LIMIT_SECONDS = 5


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

def get_redis_client():
    """Helper to get a Redis connection."""
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def get_domain_from_url(url: str) -> Optional[str]:
    """Safely extracts the domain name from a URL."""
    try:
        # Simplified split to get the domain part after http(s)://
        return url.split("//")[-1].split("/")[0]
    except IndexError:
        return None


@shared_task(bind=True, max_retries=MAX_RETRIES, name="scrape.run_smart_scrape")
def scrape_source(self, source_id: str):
    """
    The Worker Task.
    Executes the scraping pipeline for a specific source.
    Handles: Rate Limiting, Async Execution, Database Locking, Retries, DLQ.
    """
    redis_client = None
    try:
        redis_client = get_redis_client()
        
        logger.info(f"[Worker] Picked up Source ID: {source_id}")
        
        # 1. Open Database Session
        with Session(engine) as db:
            # Fetch Source to check existence and get URL for rate limiting
            query = select(Source).where(Source.id == source_id)
            source = db.exec(query).first()

            if not source:
                logger.error(f"Source {source_id} not found. Aborting.")
                return f"Aborted: Source {source_id} not found."

            # 2. Politeness Policy (Domain Rate Limiting)
            domain = get_domain_from_url(source.url)
            rate_limit_key = f"rate_limit:{domain}"
            
            # Check if this domain is 'hot'
            if domain and redis_client.exists(rate_limit_key):
                # Back off slightly to let other workers finish
                wait_time = random.uniform(5, 15)
                logger.warning(f"Rate limit active for {domain}. Retrying in {wait_time:.1f}s")
                raise self.retry(countdown=wait_time)

            # 3. EXECUTE THE SERVICE (The Heavy Lifting)
            # We initialize the Service with the DB session
            service = ScraperService(db)
            
            logger.info(f"Starting ScraperService pipeline for {source.url}")
            
            # CRITICAL: Run Async Code Synchronously
            # Since Celery is sync, we use asyncio.run to execute the async service method
            scrape_result = asyncio.run(service.execute_scrape_job(str(source.id)))
            
            # 4. Update Rate Limit Lock
            # Mark this domain as busy for 5 seconds
            if domain:
                redis_client.setex(rate_limit_key, DOMAIN_RATE_LIMIT_SECONDS, "busy")

            # 5. Update Schedule
            # Only update if successful
            source.next_scrape_time = get_next_scrape_time(
                datetime.now(timezone.utc), source.scrape_frequency
            )
            db.add(source)
            db.commit()

            return f"Success: {scrape_result}"

    except Exception as exc:
        # --- ROBUST ERROR HANDLING & DLQ ---
        if not redis_client:
             redis_client = get_redis_client()

        try:
            retry_count = self.request.retries
            
            # Calculate Exponential Backoff + Jitter
            delay = min(MAX_DELAY, BASE_DELAY * (2**retry_count))
            jitter = random.uniform(0, delay * 0.1)
            countdown = delay + jitter

            if retry_count < MAX_RETRIES:
                logger.warning(f"Task failed for {source_id}: {exc}. Retrying in {countdown:.2f}s")
                raise self.retry(exc=exc, countdown=countdown)
            else:
                # --- DEAD LETTER QUEUE (DLQ) ---
                logger.error(f"Max retries reached for {source_id}. Moving to DLQ.")
                
                dlq_entry = {
                    "task_id": self.request.id,
                    "source_id": source_id,
                    "error_message": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "args": self.request.args,
                    "kwargs": self.request.kwargs,
                }
                
                # Push to Redis List for manual inspection later
                redis_client.lpush(CELERY_DLQ_KEY, json.dumps(dlq_entry))
                return f"Failed: Moved to DLQ. Error: {exc}"
                
        except redis.RedisError as redis_exc:
            logger.critical(f"Redis Infrastructure Failure: {redis_exc}", exc_info=True)
            # Let Celery handle critical infra failures
            raise redis_exc
        except Exception:
            logger.error("Error during failure handling.", exc_info=True)
            raise exc
            
    finally:
        if redis_client:
            redis_client.close()


@shared_task(bind=True, name="scheduler.dispatch_due_sources")
def dispatch_due_sources(self):
    """
    The Scheduler (Celery Beat).
    Runs periodically (e.g., every minute).
    Finds sources that are due and dispatches scrape tasks.
    Uses Distributed Locking to prevent 'Thundering Herds'.
    """
    redis_client = None
    try:
        redis_client = get_redis_client()
    
        # 1. Acquire Non-Blocking Distributed Lock
        # "nx=True" means "Only set if key does not exist"
        lock_acquired = redis_client.set(
            DISPATCH_LOCK_KEY, "locked", nx=True, ex=LOCK_TIMEOUT_SECONDS
        )

        if not lock_acquired:
            logger.info("Dispatch task already running (Lock held). Skipping.")
            return "Skipped: Another dispatch task is already running."

        logger.info("Acquired dispatch lock. Querying database...")
        
        with Session(engine) as db:
            now = datetime.now(timezone.utc)
            
            # 2. Query Logic
            # Get sources where time is passed OR time is null (never run)
            # AND source is strictly active
            query = select(Source).where(
                (Source.next_scrape_time <= now) | (Source.next_scrape_time.is_(None)),
                Source.is_active == True
            )
            
            due_sources = db.exec(query).all()

            if not due_sources:
                logger.info("No sources due for scraping.")
                return "No sources due"

            # 3. Dispatch Logic
            for src in due_sources:
                # Push individual task to the queue
                self.app.send_task(
                    "scrape.run_smart_scrape", # Must match name defined above
                    args=[str(src.id)]
                )

            logger.info(f"Dispatched {len(due_sources)} sources to queue.")
            return f"Dispatched {len(due_sources)}"

    except Exception as e:
        logger.error(f"Dispatch failed: {e}")
        return f"Failed: {e}"
        
    finally:
        if redis_client:
            redis_client.close()