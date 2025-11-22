"""Service Handler For Jurisdiction"""

from datetime import datetime, timezone
from typing import Any, Optional, Union, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import literal, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_loader_criteria
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
            query = (
                select(Jurisdiction)
                .options(
                    with_loader_criteria(
                        Jurisdiction,
                        lambda cls: cls.is_deleted == cls.is_deleted,
                        include_aliases=True,
                    )
                )
                .where(Jurisdiction.id == jurisdiction_id)
            )

            result = await db.execute(query)
            jurisdiction = result.scalar_one_or_none()
            if not jurisdiction:
                raise HTTPException(status_code=404, detail="Jurisdiction not found")
            if jurisdiction.is_deleted:
                raise HTTPException(status_code=410, detail="This jurisdiction has been archived")
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
            active_jurisdictions = result.scalars().all()

            if not active_jurisdictions:
                raise HTTPException(
                    status_code=404, detail="No active jurisdictions found for this project"
                )

            return active_jurisdictions

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
            stmt = select(Jurisdiction)
            result = await db.execute(stmt)
            jurisdictions = result.scalars().all()

            if not jurisdictions:
                raise HTTPException(status_code=404, detail="No jurisdictions found")

            if all(j.is_deleted for j in jurisdictions):
                raise HTTPException(status_code=410, detail="All jurisdictions have been archived")

            active_jurisdictions = [j for j in jurisdictions if not j.is_deleted]

            return active_jurisdictions

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

    async def soft_delete(
        self,
        db: AsyncSession,
        jurisdiction_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
    ) -> Union[Jurisdiction, list[Jurisdiction], None]:
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
        try:
            if jurisdiction_id:
                jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
                if not jurisdiction:
                    return None
                jurisdiction.is_deleted = True
                jurisdiction.deleted_at = datetime.now(timezone.utc)
                db.add(jurisdiction)
                await db.commit()
                await db.refresh(jurisdiction)

                return jurisdiction

            elif project_id:
                stmt = (
                    update(Jurisdiction)
                    .where(cast(Any, Jurisdiction.project_id) == project_id)
                    .values(is_deleted=True, deleted_at=datetime.now(timezone.utc))
                    .returning(Jurisdiction)
                )

                result = await db.execute(stmt)
                await db.commit()
                updated_jurisdictions = list(result.scalars().all())

                return updated_jurisdictions

            else:
                raise HTTPException(
                    status_code=400, detail="Either jurisdiction_id or project_id must be provided."
                )

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

    async def get_jurisdiction_for_restoration(
        self, db: AsyncSession, jurisdiction_id: UUID
    ) -> Jurisdiction:
        """
        Retrieve a single Jurisdiction by ID for restoration purposes.

        This method will return the Jurisdiction even if it is currently archived (is_deleted=True),
        so it can be restored. If the jurisdiction does not exist at all, it raises a 404.
        Any database errors raise a 500.

        Args:
            db (AsyncSession): Database session.
            jurisdiction_id (UUID): ID of the jurisdiction.

        Returns:
            Jurisdiction: The jurisdiction record (archived or active).

        Raises:
            HTTPException: 404 if not found, 500 on DB error.
        """
        try:
            query = (
                select(Jurisdiction)
                .options(
                    with_loader_criteria(
                        Jurisdiction,
                        lambda cls: cls.is_deleted == cls.is_deleted,
                        include_aliases=True,
                    )
                )
                .where(Jurisdiction.id == jurisdiction_id)
            )
            result = await db.execute(query)
            jurisdiction = result.scalar_one_or_none()

            if not jurisdiction:
                raise HTTPException(status_code=404, detail="Jurisdiction not found")

            return jurisdiction

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def restore_all_archived_jurisdictions(
        self, db: AsyncSession, project_id: UUID | None = None
    ) -> list[Jurisdiction]:
        """
        Restore all archived jurisdictions and return the restored objects.
        """
        try:
            # Use explicit casts for comparisons to avoid DB/driver type mismatches
            stmt = (
                select(Jurisdiction)
                .options(
                    with_loader_criteria(
                        Jurisdiction,
                        lambda cls: literal(True),
                        include_aliases=True,
                    )
                )
                .where(cast(Any, Jurisdiction.is_deleted).is_(True))
            )

            if project_id is not None:
                stmt = stmt.where(cast(Any, Jurisdiction.project_id) == project_id)

            result = await db.execute(stmt)
            archived_jurisdictions = list(result.scalars().all())

            if not archived_jurisdictions:
                return []

            for j in archived_jurisdictions:
                j.is_deleted = False
                j.deleted_at = None
                db.add(j)

            await db.commit()

            for j in archived_jurisdictions:
                await db.refresh(j)

            return archived_jurisdictions

        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
