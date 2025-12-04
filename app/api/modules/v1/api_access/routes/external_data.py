from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.db.database import get_db
from app.api.core.dependencies.api_key_auth import require_api_key
from app.api.modules.v1.api_access.models.api_key import ApiKey

from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.scraping.models.source_model import Source

router = APIRouter(prefix="/external", tags=["external-api"])


@router.get("/projects")
async def get_projects(
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    q = select(Project).where(Project.org_id == api_key.organization_id)
    res = await db.execute(q)
    return res.scalars().all()


@router.get("/jurisdictions")
async def get_jurisdictions(
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    q = (
        select(Jurisdiction)
        .join(Project, Project.id == Jurisdiction.project_id)
        .where(Project.org_id == api_key.organization_id)
    )
    res = await db.execute(q)
    return res.scalars().all()

@router.get("/sources")
async def get_sources(
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    q = (
        select(Source)
        .join(Jurisdiction, Jurisdiction.id == Source.jurisdiction_id)
        .join(Project, Project.id == Jurisdiction.project_id)
        .where(Project.org_id == api_key.organization_id)
    )

    res = await db.execute(q)
    return res.scalars().all()
