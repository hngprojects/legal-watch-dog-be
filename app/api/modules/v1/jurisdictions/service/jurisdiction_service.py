"""Service Handler For Jurisdiction
"""
from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import status, HTTPException
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import false
from sqlmodel import select
from uuid import UUID
from typing import Any, cast

class JurisdictionService:

    async def get_jurisdiction_by_id(self, db: AsyncSession, jurisdiction_id: UUID):
        """Finds Jurisdiction by Id"""
        try:
            jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
            if not jurisdiction:
                raise HTTPException(status_code=404, detail="Jurisdiction not found")
            return jurisdiction
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    async def get_jurisdiction_by_name(self, db: AsyncSession, name: str):
        """Finds Jurisdiction by name"""
        stmt = select(Jurisdiction).where(
            cast(Any, Jurisdiction.name) == name,
            cast(Any, Jurisdiction.is_deleted).is_(False)
        )
        result = await db.exec(stmt)
        # ScalarResult: use first() to retrieve the first mapped object or None
        return result.first()
    
    async def create(self, db: AsyncSession, jurisdiction: Jurisdiction):
        """Create a Jurisdiction. If first in project, set parent_id to itself."""
        try:
            existing = None
            project_id = jurisdiction.project_id

            if project_id is not None:
                stmt = select(Jurisdiction).where(
                    cast(Any, Jurisdiction.project_id) == project_id,
                    cast(Any, Jurisdiction.is_deleted).is_(False),
                )
                result = await db.exec(stmt)
                existing = result.first()

            if existing is None:
                jurisdiction.parent_id = jurisdiction.id

            # Now add and persist
            db.add(jurisdiction)
            await db.commit()
            await db.refresh(jurisdiction)

            return jurisdiction
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    async def get_jurisdictions_by_project(self, db: AsyncSession, project_id: UUID):
        """Get all jurisdictions for a specific project"""
        try:
            stmt = select(Jurisdiction).where(cast(Any, Jurisdiction.project_id) == project_id, cast(Any, Jurisdiction.is_deleted).is_(False))
            result = await db.exec(stmt)
            jurisdictions = result.all()

            if not jurisdictions:
               raise HTTPException(status_code=404, detail="No jurisdictions found for this project")

            return jurisdictions

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_all_jurisdictions(self, db: AsyncSession):
        """Get all Jurisduction"""
        try:
            stmt = select(Jurisdiction).where(cast(Any, Jurisdiction.is_deleted).is_(False))
            result = await db.exec(stmt)
            jurisdictions = result.all()
            
            if not jurisdictions:
                raise HTTPException(status_code=404, detail="No jurisdictions found")
            
            return jurisdictions
        
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")           
            

    async def update(self, db: AsyncSession, jurisdiction: Jurisdiction):
        """Update a jurisdiction with error handling"""
        try:
            await db.commit()
            await db.refresh(jurisdiction)
            return jurisdiction
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=f"Integrity error: {e.orig}")
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def read(self, db: AsyncSession):
        """Read all jurisdictions with error handling"""
        try:
            stmt = select(Jurisdiction)
            result = await db.exec(stmt)
            return result.all()
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    async def soft_delete(self, db: AsyncSession, jurisdiction_id: UUID):
        """Soft delete a jurisdiction by setting is_deleted=True and deleted_at timestamp"""
        jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction:
            return None
        try:
            jurisdiction.is_deleted = True
            jurisdiction.deleted_at = datetime.now()
            db.add(jurisdiction)
            await db.commit()
            await db.refresh(jurisdiction)
            return jurisdiction
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete jurisdiction due to integrity constraints: {e.orig}"
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
               detail=f"Database error occurred while deleting jurisdiction: {str(e)}"
            )

    async def delete(self, db: AsyncSession, jurisdiction: Jurisdiction) -> bool:
        """Permanently delete a jurisdiction record from the database."""
        try:
            # Expecting a jurisdiction instance to be passed in (as tests provide)
            await db.delete(jurisdiction)
            await db.commit()
            return True
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete jurisdiction due to integrity constraints: {e.orig}"
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error occurred while deleting jurisdiction: {str(e)}"
            )