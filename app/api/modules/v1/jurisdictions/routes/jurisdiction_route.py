from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
    JurisdictionResponseSchema,
    JurisdictionUpdateSchema,
)
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import (
    JurisdictionService,
)

router = APIRouter(prefix="/jurisdictions", tags=["Jurisdictions"])

service = JurisdictionService()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=JurisdictionResponseSchema)
async def create_jurisdiction(
    payload: JurisdictionCreateSchema, db: AsyncSession = Depends(get_db)
):
    """Create a new Jurisdiction in a project"""
    jurisdiction = Jurisdiction(**payload.model_dump())
    created = await service.create(db, jurisdiction)
    return created


@router.get("/", status_code=status.HTTP_200_OK, response_model=List[JurisdictionResponseSchema])
async def get_jurisdictions(project_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    """
    Returns jurisdictions.
    - If `project_id` is provided, returns jurisdictions for that project.
    - Otherwise, returns all jurisdictions in the database.
    """
    if project_id:
        jurisdictions = await service.get_jurisdictions_by_project(db, project_id)
    else:
        jurisdictions = await service.get_all_jurisdictions(db)

    if not jurisdictions:
        raise HTTPException(status_code=404, detail="No jurisdictions found")

    return jurisdictions


@router.get(
    "/{jurisdiction_id}",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def get_jurisdiction(jurisdiction_id, db: AsyncSession = Depends(get_db)):
    """Returns a single Jurisdiction"""
    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
    if not jurisdiction:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    return jurisdiction


@router.patch(
    "/{jurisdiction_id}",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def update_jurisdiction(
    jurisdiction_id: UUID,
    payload: JurisdictionUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    """Update Jurisdiction"""
    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
    if not jurisdiction:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(jurisdiction, key, value)

    updated = await service.update(db, jurisdiction)
    return updated


@router.delete("/{jurisdiction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
    """Archives a Jurisdiction"""
    jurisdiction = await service.soft_delete(db, jurisdiction_id)
    if not jurisdiction:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    return


@router.post(
    "/{jurisdiction_id}/restore",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def restore_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
    if not jurisdiction or not jurisdiction.is_deleted:
        raise HTTPException(status_code=404, detail="Jurisdiction not found or not deleted")

    jurisdiction.is_deleted = False
    jurisdiction.deleted_at = None
    restored = await service.update(db, jurisdiction)
    return restored
