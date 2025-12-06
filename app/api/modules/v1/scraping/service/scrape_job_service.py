"""
Service layer for scrape job operations.

Handles background scrape execution and job lifecycle management.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlmodel import select

from app.api.core.config import settings
from app.api.db.database import AsyncSessionLocal
from app.api.events.builders import build_scrape_job_event
from app.api.events.factory import get_event_publisher
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.service.scraper_service import ScraperService

logger = logging.getLogger("app")


class ScrapeJobService:
    """Service for managing scrape jobs and background execution."""

    @staticmethod
    async def execute_scrape_job_background(job_id: uuid.UUID, source_id: uuid.UUID) -> None:
        """
        Execute a scrape job asynchronously in the background.

        Creates its own database session to avoid session lifecycle issues.
        Updates the job status throughout execution and handles errors gracefully.

        Args:
            job_id (uuid.UUID): The scrape job ID to update.
            source_id (uuid.UUID): The source ID to scrape.
        """
        try:
            async with AsyncSessionLocal() as db:
                job_query = select(ScrapeJob).where(ScrapeJob.id == job_id)
                job_result = await db.execute(job_query)
                job = job_result.scalars().first()

                if not job:
                    logger.error(f"ScrapeJob {job_id} not found in background task")
                    return

                job.status = ScrapeJobStatus.IN_PROGRESS
                job.started_at = datetime.now(timezone.utc)
                await db.commit()
                await ScrapeJobService._publish_scrape_job_update(job)

                try:
                    service = ScraperService(db)
                    scrape_result = await service.execute_scrape_job(str(source_id))

                    job.status = ScrapeJobStatus.COMPLETED
                    job.result = scrape_result
                    job.completed_at = datetime.now(timezone.utc)

                    if scrape_result and "data_revision_id" in scrape_result:
                        try:
                            job.data_revision_id = uuid.UUID(scrape_result["data_revision_id"])
                        except (ValueError, TypeError):
                            data_rev_id = scrape_result.get("data_revision_id")
                            logger.warning(
                                f"Invalid data_revision_id in scrape result: {data_rev_id}"
                            )

                    if scrape_result:
                        job.is_baseline = scrape_result.get("is_baseline", False)

                    logger.info(f"Background scrape completed for source {source_id}, job {job_id}")

                except Exception as e:
                    logger.error(
                        f"Background scrape failed for source {source_id}, job {job_id}: {str(e)}",
                        exc_info=True,
                    )
                    job.status = ScrapeJobStatus.FAILED
                    job.error_message = (
                        "Scrape execution failed. Please try again or contact support "
                        "if the issue persists."
                    )
                    job.completed_at = datetime.now(timezone.utc)

                await db.commit()
                await ScrapeJobService._publish_scrape_job_update(job)

        except Exception as e:
            logger.error(
                f"Critical error in background scrape task for job {job_id}: {str(e)}",
                exc_info=True,
            )

    @staticmethod
    def queue_scrape_job(job_id: uuid.UUID, source_id: uuid.UUID) -> None:
        """
        Queue a scrape job for background execution.

        Uses asyncio.create_task for fire-and-forget execution.

        Args:
            job_id (uuid.UUID): The scrape job ID.
            source_id (uuid.UUID): The source ID to scrape.
        """
        task = asyncio.create_task(
            ScrapeJobService.execute_scrape_job_background(job_id, source_id)
        )
        task.add_done_callback(
            lambda t: logger.error("Exception in background scrape job", exc_info=t.exception())
            if t.exception()
            else None
        )

    @staticmethod
    async def _publish_scrape_job_update(job: ScrapeJob) -> None:
        """Publish scrape job updates over websockets when enabled.

        Args:
            job (ScrapeJob): The job instance that changed state.

        Returns:
            None

        Raises:
            RuntimeError: If the event publisher cannot be created.

        Examples:
            >>> await ScrapeJobService._publish_scrape_job_update(job)
        """

        if not settings.ENABLE_REALTIME_WEBSOCKETS:
            return
        publisher = await get_event_publisher()
        event = build_scrape_job_event(job)
        await publisher.publish(event)
