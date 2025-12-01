"""API endpoints for manual scraping operations.

Provides endpoints for:
- POST /scraping/sources/{source_id}/scrape - Trigger manual scrape task
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.routes.docs.manual_scrape_docs import (
    trigger_manual_scrape_custom_errors,
    trigger_manual_scrape_custom_success,
    trigger_manual_scrape_responses,
)
from app.api.modules.v1.scraping.service.tasks import scrape_source
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(
    prefix="/scraping",
    tags=["Scraping"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)
logger = logging.getLogger("app")


@router.post(
    "/sources/{source_id}/scrape",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual scrape for a source",
    responses=trigger_manual_scrape_responses,
)
async def trigger_manual_scrape(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger the background scraping task for a specific source.

    This endpoint verifies the source exists and is active, then queues
    a Celery task to perform the scraping asynchronously. The task runs
    in the background and returns immediately with a task ID for tracking.

    Args:
        source_id (UUID): The unique identifier of the source to scrape.
        db (AsyncSession): Database session dependency.
        current_user (User): Authenticated user.

    Returns:
        dict: Response containing:
            - message (str): Status message
            - task_id (str): Celery task ID for tracking
            - source_id (str): Source UUID
            - status (str): Task status (PENDING)

    Raises:
        HTTPException(404): If the source is not found.
        HTTPException(400): If the source is inactive or deleted.


    """
    logger.info(f"User {current_user.id} triggering manual scrape for source {source_id}")

    query = select(Source).where(Source.id == source_id)
    result = await db.execute(query)
    source = result.scalars().first()

    if not source:
        logger.warning(f"Manual scrape attempt for non-existent source {source_id}")
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Source not found",
            error="SOURCE_NOT_FOUND",
        )

    if not source.is_active or source.is_deleted:
        logger.warning(
            f"Manual scrape attempt for inactive/deleted source {source_id} "
            f"(is_active={source.is_active}, is_deleted={source.is_deleted})"
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Cannot scrape inactive or deleted source",
            error="SOURCE_INACTIVE_OR_DELETED",
        )

    try:
        task_info = scrape_source.delay(str(source.id))

        logger.info(f"Scrape task queued for source {source_id} with task_id {task_info.id}")

        return success_response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Scrape job queued successfully",
            data={
                "task_id": str(task_info.id),
                "source_id": str(source.id),
                "status": "PENDING",
            },
        )

    except Exception as e:
        logger.error(f"Failed to queue scrape task for source {source_id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to queue scrape task",
            error="TASK_QUEUE_ERROR",
            errors={"details": str(e)},
        )


trigger_manual_scrape._custom_errors = trigger_manual_scrape_custom_errors
trigger_manual_scrape._custom_success = trigger_manual_scrape_custom_success
