from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.core.dependencies.auth import TenantGuard
from app.api.db.database import get_db
from app.api.modules.v1.search.schemas.search_schema import (
    SearchRequest,
    SearchResponse,
)
from app.api.modules.v1.search.service.search_service import SearchService

router = APIRouter(prefix="/data-revisions", tags=["Data Revision Search"])


@router.post(
    "/",
    response_model=SearchResponse,
    dependencies=[Depends(TenantGuard)],
)
async def search_data_revisions(
    request: SearchRequest,
    db: Session = Depends(get_db),
    tenant: TenantGuard = Depends(),
):
    """
    Full-text search for DataRevision entities.

    Args:
        request: Search request containing query string, filters, and pagination
        tenant: TenantGuard dependency enforcing auth & org access
        db: Database session dependency

    Returns:
        SearchResponse: Search results with matching revisions and metadata
    """

    if not tenant.user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Optionally, enforce organization filter for multi-tenant isolation
    org_id = getattr(tenant.user, "organization_id", None)
    if not org_id:
        raise HTTPException(status_code=403, detail="User does not belong to an organization")

    service = SearchService(db)
    return await service.search(request, org_id=org_id)
