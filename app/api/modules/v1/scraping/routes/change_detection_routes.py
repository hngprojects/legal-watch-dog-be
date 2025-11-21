# routers/revisions.py
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
from app.api.modules.v1.scraping.service.change_detection_service import ChangeDetectionService
from app.api.modules.v1.scraping.service.mock_ai_summary import MockAIService

router = APIRouter(prefix="/revisions", tags=["revisions"])


@router.post("/create", response_model=RevisionWithDiffResponse)
async def create_revision_with_change_detection(
    revision_data: RevisionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new revision and automatically detect changes.
    """
    try:
        # Step 1: Generate AI summary (MOCK)
        ai_summary = MockAIService.generate_summary(revision_data.raw_content)

        # Step 2: Run change detection service
        detection_service = ChangeDetectionService(db)
        new_revision, change_diff = await detection_service.create_revision_with_detection(
            source_id=revision_data.source_id,
            scraped_at=datetime.utcnow(),
            status=revision_data.status,
            raw_content=revision_data.raw_content,
            extracted_data=revision_data.extracted_data,
            ai_summary=ai_summary
        )

        # Step 3: Format response
        return RevisionWithDiffResponse(
            revision=RevisionResponse.from_orm(new_revision),
            change_diff=ChangeDiffResponse.from_orm(change_diff) if change_diff else None
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating revision: {str(e)}")


# @router.get("/source/{source_id}/history", response_model=List[RevisionResponse])
# async def get_source_revision_history(
#     source_id: str,
#     limit: int = 10,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Get revision history for a specific source.
#     """
#     try:
#         result = await db.execute(
#             select(DataRevision)
#             .where(DataRevision.source_id == source_id)
#             .where(DataRevision.deleted_at.is_(None))
#             .order_by(DataRevision.created_at.desc())
#             .limit(limit)
#         )
#         revisions = result.scalars().all()
#         return revisions
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching revisions: {str(e)}")


# @router.get("/changes/{source_id}", response_model=List[RevisionResponse])
# async def get_detected_changes(
#     source_id: str,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Get all detected changes for a source.
#     Only returns revisions where changes were detected.
#     """
#     try:
#         result = await db.execute(
#             select(DataRevision)
#             .where(DataRevision.source_id == source_id)
#             .where(DataRevision.was_change_detected.is_(True))
#             .where(DataRevision.deleted_at.is_(None))
#             .order_by(DataRevision.created_at.desc())
#         )
#         changes = result.scalars().all()
#         return changes
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching detected changes: {str(e)}")
