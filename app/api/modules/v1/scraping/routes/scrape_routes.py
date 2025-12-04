"""
API routes for Scrape Job operations.

Provides endpoints for:
- POST /scrapes/{source_id} - Trigger manual scrape for a source
- GET /scrapes/{source_id}/{job_id} - Get scrape job status
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import AsyncSessionLocal, get_db
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.routes.docs.scrape_routes_docs import (
    get_scrape_job_status_custom_errors,
    get_scrape_job_status_custom_success,
    get_scrape_job_status_responses,
    manual_scrape_trigger_custom_errors,
    manual_scrape_trigger_custom_success,
    manual_scrape_trigger_responses,
)
from app.api.modules.v1.scraping.schemas.scrape_job_schema import ScrapeJobResponse
from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(
    prefix="/scrapes",
    tags=["Scrapes"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)
logger = logging.getLogger("app")


async def _run_scrape_background(job_id: uuid.UUID, source_id: uuid.UUID) -> None:
    """
    Background task that executes the scrape job asynchronously.

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
                        logger.warning(f"Invalid data_revision_id in scrape result: {data_rev_id}")

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

    except Exception as e:
        logger.error(
            f"Critical error in background scrape task for job {job_id}: {str(e)}",
            exc_info=True,
        )


@router.post(
    "/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
    responses=manual_scrape_trigger_responses,
)
async def manual_scrape_trigger(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger an asynchronous scrape job for a specific source.

    This endpoint queues a scrape job and returns immediately with a job ID.
    Use the job status endpoint to poll for completion.

    Concurrency is controlled per source - only one active job (PENDING or IN_PROGRESS)
    is allowed per source at a time. If a job is already running, a 409 Conflict
    response is returned.

    Args:
        source_id (uuid.UUID): The UUID of the source to scrape.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: 202 Accepted with job_id for polling, or error response.

    Raises:
        HTTPException: 404 if source not found, 400 if source inactive,
                      409 if scrape already in progress.
    """
    query = select(Source).where(Source.id == source_id)
    result = await db.execute(query)
    source = result.scalars().first()

    if not source:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Source not found",
            error="SOURCE_NOT_FOUND",
        )

    if not source.is_active:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Cannot scrape inactive source. Please enable it first.",
            error="SOURCE_INACTIVE",
        )

    try:
        job = ScrapeJob(
            source_id=source_id,
            status=ScrapeJobStatus.PENDING,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    except IntegrityError:
        await db.rollback()
        return error_response(
            status_code=status.HTTP_409_CONFLICT,
            message="A scrape is already in progress for this source. "
            "Please wait for it to complete.",
            error="SCRAPE_IN_PROGRESS",
        )

    asyncio.create_task(_run_scrape_background(job.id, source_id))

    logger.info(f"User {current_user.id} triggered scrape job {job.id} for source {source_id}")

    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Scrape job queued successfully",
        data={
            "job_id": str(job.id),
            "source_id": str(source_id),
            "status": job.status.value,
        },
    )


manual_scrape_trigger._custom_errors = manual_scrape_trigger_custom_errors
manual_scrape_trigger._custom_success = manual_scrape_trigger_custom_success


@router.get(
    "/{source_id}/{job_id}",
    status_code=status.HTTP_200_OK,
    responses=get_scrape_job_status_responses,
)
async def get_scrape_job_status(
    source_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of a scrape job.

    Use this endpoint to poll for job completion after triggering a manual scrape.
    Returns the current status and, if completed, the scrape results or error message.

    Args:
        source_id (uuid.UUID): The UUID of the source.
        job_id (uuid.UUID): The UUID of the scrape job.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Success response with job status and results.

    Raises:
        HTTPException: 404 if job not found or doesn't belong to the source.
    """
    query = select(ScrapeJob).where(
        ScrapeJob.id == job_id,
        ScrapeJob.source_id == source_id,
    )
    result = await db.execute(query)
    job = result.scalars().first()

    if not job:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Scrape job not found",
            error="JOB_NOT_FOUND",
        )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Scrape job status retrieved successfully",
        data=ScrapeJobResponse.model_validate(job).model_dump(mode="json"),
    )


get_scrape_job_status._custom_errors = get_scrape_job_status_custom_errors
get_scrape_job_status._custom_success = get_scrape_job_status_custom_success
