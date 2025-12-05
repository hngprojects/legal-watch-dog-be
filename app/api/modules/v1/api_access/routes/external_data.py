from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.api_key_auth import require_api_key
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.api_access.models.api_key import ApiKey

# NEW — import schemas from external file
from app.api.modules.v1.api_access.schemas.api_key_schema import (
    JurisdictionResponse,
    ProjectResponse,
    SourceResponse,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.source_model import Source

router = APIRouter(prefix="/external", tags=["external-api"])


@router.get("/projects", response_model=List[ProjectResponse])
async def get_projects(
    api_key: ApiKey = Depends(require_api_key),
    _: None = Depends(require_billing_access),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """
    Get all projects for the organization associated with the provided API key.

    Args:
        api_key (ApiKey): The API key object, injected by dependency.
        db (AsyncSession): Async SQLAlchemy session.

    Returns:
        list[ProjectResponse]: List of projects.
    """
    q = select(Project).where(Project.org_id == api_key.organization_id)
    res = await db.execute(q)
    return res.scalars().all()


@router.get("/jurisdictions", response_model=List[JurisdictionResponse])
async def get_jurisdictions(
    api_key: ApiKey = Depends(require_api_key),
    _: None = Depends(require_billing_access),
    db: AsyncSession = Depends(get_db),
) -> list[JurisdictionResponse]:
    """
    Get all jurisdictions for projects associated with the API key's organization.

    Args:
        api_key (ApiKey): The API key object, injected by dependency.
        db (AsyncSession): Async SQLAlchemy session.

    Returns:
        list[JurisdictionResponse]: List of jurisdictions.
    """
    q = (
        select(Jurisdiction)
        .join(Project, Project.id == Jurisdiction.project_id)
        .where(Project.org_id == api_key.organization_id)
    )
    res = await db.execute(q)
    return res.scalars().all()


@router.get("/sources", response_model=List[SourceResponse])
async def get_sources(
    api_key: ApiKey = Depends(require_api_key),
    _: None = Depends(require_billing_access),
    db: AsyncSession = Depends(get_db),
) -> list[SourceResponse]:
    """
    Get all sources for jurisdictions associated with projects of the API key's organization.

    Args:
        api_key (ApiKey): The API key object, injected by dependency.
        db (AsyncSession): Async SQLAlchemy session.

    Returns:
        list[SourceResponse]: List of sources.
    """
    q = (
        select(Source)
        .join(Jurisdiction, Jurisdiction.id == Source.jurisdiction_id)
        .join(Project, Project.id == Jurisdiction.project_id)
        .where(Project.org_id == api_key.organization_id)
    )
    res = await db.execute(q)
    return res.scalars().all()
