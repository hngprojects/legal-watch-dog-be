from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.scraping.schemas.change_detection_schemas import (
    ChangeDiffResponse,
    RevisionCreate,
    RevisionResponse,
    RevisionWithDiffResponse,
)
from app.api.modules.v1.scraping.service.change_detection_service import (
    ChangeDetectionService,
)
from app.api.modules.v1.scraping.service.mock_ai_summary import MockAIService

router = APIRouter(prefix="/revisions", tags=["revisions"])


@router.post(
    "/create",
    response_model=RevisionWithDiffResponse,
    summary="Create a new revision (Not Ready)",
    description="""
    **This endpoint is not yet fully implemented.**
    """,
)
async def create_revision_with_change_detection(
    revision_data: RevisionCreate, db: AsyncSession = Depends(get_db)
):
    """
    Create a new revision, generate an AI summary, and detect changes.

    Args:
        revision_data (RevisionCreate):
            Incoming revision payload containing raw content, source_id,
            extracted data, and status.

        db (AsyncSession):
            Database session dependency injected by FastAPI.

    Returns:
        RevisionWithDiffResponse:
            The newly created revision along with detected change differences
            (if any).

    Raises:
        HTTPException (500):
            Raised when an unexpected error occurs during revision creation or
            change detection.
    """
    try:
        ai_summary = MockAIService.generate_summary(revision_data.raw_content)

        detection_service = ChangeDetectionService(db)
        new_revision, change_diff = await detection_service.create_revision_with_detection(
            source_id=revision_data.source_id,
            scraped_at=datetime.utcnow(),
            status=revision_data.status,
            minio_object_key=revision_data.minio_object_key,
            raw_content=revision_data.raw_content,
            extracted_data=revision_data.extracted_data,
            ai_summary=ai_summary,
        )

        return RevisionWithDiffResponse(
            revision=RevisionResponse.from_orm(new_revision),
            change_diff=(ChangeDiffResponse.from_orm(change_diff) if change_diff else None),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating revision: {str(e)}")
