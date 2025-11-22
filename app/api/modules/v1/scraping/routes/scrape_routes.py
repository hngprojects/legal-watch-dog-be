from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.core.dependencies.database import get_db
from app.api.modules.v1.scraping.models.source_model import Source

# Import the Celery task (we will create this in step 2)
from app.api.modules.v1.scraping.service.scraping_tasks import run_smart_scrape_task

router = APIRouter(prefix="/sources", tags=["Scraping"])

@router.post("/{source_id}/scrape_manual", status_code=status.HTTP_202_ACCEPTED)
async def trigger_manual_scrape(
    source_id: UUID, 
    db: Session = Depends(get_db)
):
    """
    Manually triggers the scraping task for a specific source.
    Returns immediately so the API doesn't hang.
    """
    # 1. Validate Source Exists
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # 2. Dispatch to Celery (Background Worker)
    # .delay() is the standard way to push to the queue
    task = run_smart_scrape_task.delay(str(source_id))

    return {
        "message": "Scraping task initiated successfully",
        "task_id": task.id,
        "source_id": source_id
    }