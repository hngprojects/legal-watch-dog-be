from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.modules.v1.search.schemas.search_schema import (
    SearchRequest,
    SearchResponse,
)
from app.api.modules.v1.search.service.search_service import SearchService

router = APIRouter(prefix="/data-revisions", tags=["Data Revision Search"])


@router.post("/", response_model=SearchResponse)
async def search_data_revisions(request: SearchRequest, db: Session = Depends(get_db)):
    """
    Full-text search specifically for DataRevision entities.
    """
    service = SearchService(db)
    return await service.search(request)
