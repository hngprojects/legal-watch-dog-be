"""Service Handler For Jurisdiction"""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction


class JurisdictionService:
    async def get_jurisdiction_by_id(self, db: AsyncSession, jurisdiction_id: UUID):
        """
        Retrieve a single Jurisdiction by its unique identifier.

        This method queries the database for a Jurisdiction with the given `jurisdiction_id`.
        If no matching record is found, it raises an HTTPException with status code 404.
        Any database errors during the query will raise an HTTPException with status code 500.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            jurisdiction_id (UUID): The unique identifier of the Jurisdiction to retrieve.

        Returns:
            Jurisdiction: The matching Jurisdiction instance from the database.

        Raises:
            HTTPException:
                - 404 if the Jurisdiction does not exist.
                - 500 if a database error occurs.
        """
        try:
            jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
            if not jurisdiction:
                raise HTTPException(status_code=404, detail="Jurisdiction not found")
            return jurisdiction
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_jurisdiction_by_name(self, db: AsyncSession, name: str):
        """
        Retrieve a single Jurisdiction by its name.

        This method queries the database for a Jurisdiction with the specified `name`
        that has not been soft-deleted (`is_deleted=False`). If multiple jurisdictions
        match the name, only the first one is returned.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            name (str): The name of the Jurisdiction to retrieve.

        Returns:
            Optional[Jurisdiction]: The first matching Jurisdiction instance if found,
            otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        stmt = select(Jurisdiction).where(
            cast(Any, Jurisdiction.name) == name,
            cast(Any, Jurisdiction.is_deleted).is_(False),
        )
        result = await db.execute(stmt)
        # ScalarResult: use first() to retrieve the first mapped object or None
        return result.first()

    async def create(self, db: AsyncSession, jurisdiction: Jurisdiction):
        """Create a Jurisdiction. If first in project, set parent_id to itself."""
        try:
            # existing = None
            # project_id = jurisdiction.project_id

            # if project_id is not None:
            #     stmt = select(Jurisdiction).where(
            #         cast(Any, Jurisdiction.project_id) == project_id,
            #         cast(Any, Jurisdiction.is_deleted).is_(False),
            #     )
            #     result = await db.execute(stmt)
            #     existing = result.first()

            # if existing is None:
            #     jurisdiction.parent_id = jurisdiction.id

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
        """
        Retrieve all active jurisdictions associated with a specific project.

        This method queries the database for all Jurisdiction records where
        `project_id` matches the given value and `is_deleted` is False (i.e., not soft-deleted).
        If no jurisdictions are found for the project, an HTTPException with status code 404
        is raised. Any database errors during the query will raise an
        HTTPException with status code 500.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            project_id (UUID): The unique identifier of the project
            whose jurisdictions are being retrieved.

        Returns:
            List[Jurisdiction]: A list of Jurisdiction instances associated with the project.

        Raises:
            HTTPException:
                - 404 if no jurisdictions are found for the project.
                - 500 if a database error occurs.
        """
        try:
            stmt = select(Jurisdiction).where(
                cast(Any, Jurisdiction.project_id) == project_id,
                cast(Any, Jurisdiction.is_deleted).is_(False),
            )
            result = await db.execute(stmt)
            jurisdictions = result.scalars().all()

            if not jurisdictions:
                raise HTTPException(
                    status_code=404, detail="No jurisdictions found for this project"
                )

            return jurisdictions

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_all_jurisdictions(self, db: AsyncSession):
        """
        Retrieve all active jurisdictions in the system.

        This method queries the database for all Jurisdiction records where `is_deleted` is False
        (i.e., not soft-deleted). If no jurisdictions are found,
        an HTTPException with status code 404
        is raised. Any database errors during the query
        will raise an HTTPException with status code 500.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.

        Returns:
            List[Jurisdiction]: A list of all active Jurisdiction instances.

        Raises:
            HTTPException:
                - 404 if no jurisdictions are found.
                - 500 if a database error occurs.
        """
        try:
            stmt = select(Jurisdiction).where(cast(Any, Jurisdiction.is_deleted).is_(False))
            result = await db.execute(stmt)
            jurisdictions = result.scalars().all()

            if not jurisdictions:
                raise HTTPException(status_code=404, detail="No jurisdictions found")

            return jurisdictions

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def update(self, db: AsyncSession, jurisdiction: Jurisdiction):
        """
        Persist updates to an existing Jurisdiction in the database.

        This method commits any changes made to the given `jurisdiction` instance and refreshes it
        from the database to ensure the latest state is returned. It handles database errors and
        integrity constraints by rolling back the transaction and raising an HTTPException.

        Args:
            db (AsyncSession): The asynchronous database session used to commit changes.
            jurisdiction (Jurisdiction): The Jurisdiction instance with updated fields.

        Returns:
            Jurisdiction: The updated Jurisdiction instance reflecting persisted changes.

        Raises:
            HTTPException:
                - 400 if an integrity constraint is violated
                (e.g., unique or foreign key constraints).
                - 500 if a general database error occurs during commit or refresh.
        """
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
        """
        Retrieve all jurisdictions from the database, including soft-deleted ones.

        This method queries the database for all Jurisdiction records without filtering
        by `is_deleted`. It handles database errors by raising an HTTPException with
        a 500 status code if any issues occur during the query execution.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.

        Returns:
            List[Jurisdiction]: A list of all Jurisdiction instances in the database.

        Raises:
            HTTPException:
                - 500 if a database error occurs while retrieving jurisdictions.
        """
        try:
            stmt = select(Jurisdiction)
            result = await db.execute(stmt)
            return result.all()
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def soft_delete(self, db: AsyncSession, jurisdiction_id: UUID):
        """
        Soft delete a Jurisdiction by marking it as deleted without removing it from the database.

        This method sets the `is_deleted` flag to True and updates the `deleted_at` timestamp
        to the current time for the jurisdiction identified by `jurisdiction_id`. The record
        remains in the database for historical reference or potential restoration.

        Args:
            db (AsyncSession): The asynchronous database session used to persist changes.
            jurisdiction_id (UUID): The unique identifier of the Jurisdiction to be soft-deleted.

        Returns:
            Optional[Jurisdiction]: The soft-deleted Jurisdiction instance if found,
            otherwise None if no matching jurisdiction exists.

        Raises:
            HTTPException:
                - 400 if the soft delete violates integrity constraints
                (e.g., foreign key dependencies).
                - 500 if a database error occurs during the update.
        """
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
                detail=f"Cannot delete jurisdiction due to integrity constraints: {e.orig}",
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error occurred while deleting jurisdiction: {str(e)}",
            )

    async def delete(self, db: AsyncSession, jurisdiction: Jurisdiction) -> bool:
        """
        Permanently delete a Jurisdiction record from the database.

        This method removes the given `jurisdiction` instance from the database and commits
        the transaction. Unlike `soft_delete`, this operation irreversibly deletes the record.

        Args:
            db (AsyncSession): The asynchronous database session used to execute the deletion.
            jurisdiction (Jurisdiction): The Jurisdiction instance to be permanently removed.

        Returns:
            bool: True if the deletion was successful.

        Raises:
            HTTPException:
                - 400 if the deletion violates integrity constraints (e.g., related records exist).
                - 500 if a database error occurs during the deletion.
        """
        try:
            # Expecting a jurisdiction instance to be passed in (as tests provide)
            await db.delete(jurisdiction)
            await db.commit()
            return True
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete jurisdiction due to integrity constraints: {e.orig}",
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error occurred while deleting jurisdiction: {str(e)}",
            )
