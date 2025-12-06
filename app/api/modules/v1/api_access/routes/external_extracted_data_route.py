import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.api_key_auth import api_key_has_scope, get_api_key_from_header
from app.api.db.database import get_db
from app.api.utils.response_payloads import success_response

router = APIRouter(prefix="/external", tags=["External Extracted Data"])


@router.get("/sources/{source_id}/extracted-data", status_code=status.HTTP_200_OK)
async def get_source_extracted_data(
    source_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    required_scope = "read:source"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    if getattr(api_key, "organization_id", None):
        stmt_check = select(Source).where(
            and_(Source.id == source_id, Source.jurisdiction_id.isnot(None))
        )
        res_check = await db.execute(stmt_check)
        src = res_check.scalars().first()
        if not src:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction

        stmt_j = select(Jurisdiction).where(Jurisdiction.id == src.jurisdiction_id)
        rj = await db.execute(stmt_j)
        jur = rj.scalars().first()
        if not jur:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found"
            )

        from app.api.modules.v1.projects.models.project_model import Project

        stmt_p = select(Project).where(Project.id == jur.project_id)
        rp = await db.execute(stmt_p)
        proj = rp.scalars().first()
        if not proj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        if getattr(api_key, "organization_id", None) != getattr(proj, "org_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch"
            )

    stmt = select(DataRevision).where(DataRevision.source_id == source_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Extracted data retrieved",
        data={"revisions": payload},
    )


@router.get("/jurisdictions/{jurisdiction_id}/extracted-data", status_code=status.HTTP_200_OK)
async def get_jurisdiction_extracted_data(
    jurisdiction_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    required_scope = "read:jurisdiction"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    if getattr(api_key, "organization_id", None):
        stmt_proj = (
            select(Project)
            .join(Jurisdiction, Jurisdiction.project_id == Project.id)
            .where(Jurisdiction.id == jurisdiction_id)
        )
        rp = await db.execute(stmt_proj)
        proj = rp.scalars().first()
        if not proj or getattr(api_key, "organization_id", None) != getattr(proj, "org_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch"
            )

    stmt = (
        select(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .where(Source.jurisdiction_id == jurisdiction_id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Extracted data retrieved",
        data={"revisions": payload},
    )


@router.get("/projects/{project_id}/extracted-data", status_code=status.HTTP_200_OK)
async def get_project_extracted_data(
    project_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    required_scope = "read:project"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    if getattr(api_key, "organization_id", None):
        stmt_p = select(Project).where(Project.id == project_id)
        rp = await db.execute(stmt_p)
        proj = rp.scalars().first()
        if not proj or getattr(api_key, "organization_id", None) != getattr(proj, "org_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch"
            )

    stmt = (
        select(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
        .where(Jurisdiction.project_id == project_id)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Extracted data retrieved",
        data={"revisions": payload},
    )
