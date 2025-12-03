from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlmodel import select

from app.api.core.dependencies.auth import TenantGuard
from app.api.db.database import get_db
from app.api.modules.v1.organization.models.user_organization_model import (
    UserOrganization,
)
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
    membership = await db.scalar(
        select(UserOrganization).where(
            UserOrganization.user_id == tenant.user.id, UserOrganization.is_active
        )
    )
    if not membership:
        raise HTTPException(
            status_code=403, detail="User does not belong to an active organization"
        )
    org_id = membership.organization_id

    service = SearchService(db)
    return await service.search(request, org_id=org_id)
