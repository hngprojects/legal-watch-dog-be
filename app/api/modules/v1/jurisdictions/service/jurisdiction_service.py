"""Service Handler For Jurisdiction"""

from datetime import datetime, timezone
from typing import Any, Optional, Union, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import literal, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlmodel import select

from app.api.core.dependencies.auth import get_current_user
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.users_model import User


async def filter_archived_recursive(jurisdiction: Jurisdiction, db: AsyncSession):
    stmt = select(Jurisdiction).where(Jurisdiction.parent_id == jurisdiction.id)
    result = await db.execute(stmt)
    active_children = [c for c in result.scalars().all() if not c.is_deleted]

    jurisdiction.__dict__["children"] = active_children

    for child in active_children:
        await filter_archived_recursive(child, db)

    return jurisdiction


async def _soft_delete_jurisdiction(jurisdiction: Jurisdiction, db: AsyncSession):
    jurisdiction.is_deleted = True
    jurisdiction.deleted_at = datetime.now(timezone.utc)
    db.add(jurisdiction)

    stmt = select(Jurisdiction).where(Jurisdiction.parent_id == jurisdiction.id)
    result = await db.execute(stmt)
    children = result.scalars().all()

    for child in children:
        await _soft_delete_jurisdiction(child, db)


async def _restore_jurisdiction_recursive(jurisdiction: "Jurisdiction", db: AsyncSession):
    """
    Recursively restore a jurisdiction and its children.
    """
    jurisdiction.is_deleted = False
    jurisdiction.deleted_at = None
    db.add(jurisdiction)

    children = getattr(jurisdiction, "children", None)

    if children is None:
        stmt = select(Jurisdiction).where(Jurisdiction.parent_id == jurisdiction.id)
        result = await db.execute(stmt)
        children = result.scalars().all()

    for child in children:
        await _restore_jurisdiction_recursive(child, db)


class JurisdictionService:
    def _serialize_jurisdiction(self, jurisdiction: Jurisdiction) -> dict:
        """Convert a Jurisdiction ORM object into a plain dict including nested children.

        This ensures the returned structure is JSON-serializable and contains the
        nested `children` produced by `filter_archived_recursive`.
        """
        data = {
            "id": getattr(jurisdiction, "id", None),
            "project_id": getattr(jurisdiction, "project_id", None),
            "parent_id": getattr(jurisdiction, "parent_id", None),
            "name": getattr(jurisdiction, "name", None),
            "description": getattr(jurisdiction, "description", None),
            "prompt": getattr(jurisdiction, "prompt", None),
            "scrape_output": getattr(jurisdiction, "scrape_output", None),
            "created_at": getattr(jurisdiction, "created_at", None),
            "updated_at": getattr(jurisdiction, "updated_at", None),
            "deleted_at": getattr(jurisdiction, "deleted_at", None),
            "is_deleted": getattr(jurisdiction, "is_deleted", False),
        }

        children = getattr(jurisdiction, "children", None)
        if children is None:
            children = jurisdiction.__dict__.get("children", [])

        data["children"] = [self._serialize_jurisdiction(c) for c in children] if children else []

        return data

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

            if getattr(jurisdiction, "is_deleted", False):
                try:
                    await db.refresh(jurisdiction)
                except Exception:
                    pass

            if getattr(jurisdiction, "is_deleted", False):
                raise HTTPException(status_code=410, detail="This jurisdiction has been archived")

            await filter_archived_recursive(jurisdiction, db)

            return self._serialize_jurisdiction(jurisdiction)

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
        return result.first()

    async def create(self, db: AsyncSession, jurisdiction: Jurisdiction):
        """Create a Jurisdiction. If first in project, set parent_id to itself."""
        try:
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
        Retrieve all active jurisdictions associated with a specific project
        including nested children.

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
                Jurisdiction.parent_id.is_(None),  # type: ignore
            )
            result = await db.execute(stmt)
            active_jurisdictions = result.scalars().all()

            if not active_jurisdictions:
                raise HTTPException(
                    status_code=404, detail="No active jurisdictions found for this project"
                )

            for jurisdiction in active_jurisdictions:
                await filter_archived_recursive(jurisdiction, db)

            return [self._serialize_jurisdiction(j) for j in active_jurisdictions]

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_all_jurisdictions(self, db: AsyncSession):
        """
        Retrieve all active jurisdictions in the system.
        Flat Structure (non-nested)

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

            try:
                if getattr(jurisdiction, "is_deleted", False):
                    await _soft_delete_jurisdiction(jurisdiction, db)
                    await db.commit()
                    await db.refresh(jurisdiction)
                else:
                    try:
                        await self.restore_jurisdiction_and_children(db, jurisdiction.id)
                    except Exception:
                        await _restore_jurisdiction_recursive(jurisdiction, db)
                        await db.commit()
                        await db.refresh(jurisdiction)
            except Exception:
                pass

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
                await _soft_delete_jurisdiction(jurisdiction, db)
                await db.commit()
                await db.refresh(jurisdiction)

                return jurisdiction

            elif project_id:
                stmt = (
                    select(Jurisdiction)
                    .where(Jurisdiction.project_id == project_id, Jurisdiction.parent_id.is_(None))  # type: ignore
                    .options(selectinload(Jurisdiction.children))
                )

                result = await db.execute(stmt)
                await db.commit()
                updated_jurisdictions = list(result.scalars().all())
                if not updated_jurisdictions:
                    return []

                for jurisdiction in updated_jurisdictions:
                    await _soft_delete_jurisdiction(jurisdiction, db)

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
        self, db: AsyncSession, jurisdiction_id: UUID, restore_nested: bool = False
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

            if restore_nested:
                await _restore_jurisdiction_recursive(jurisdiction, db)
                await db.commit()
                await db.refresh(jurisdiction)

            return jurisdiction
        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def restore_jurisdiction_and_children(self, db: AsyncSession, jurisdiction_id: UUID):
        """
        Restore a jurisdiction and all its descendant jurisdictions using a
        bulk UPDATE. This avoids ORM lifecycle event DB I/O that can trigger
        "greenlet_spawn" errors when running under an async engine.

        Returns a serialized nested jurisdiction (dict) for predictable JSON output.
        """
        try:
            query = select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
            result = await db.execute(query)
            jurisdiction = result.scalar_one_or_none()
            if not jurisdiction:
                raise HTTPException(status_code=404, detail="Jurisdiction not found")

            cte_sql = text(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id, parent_id FROM jurisdictions WHERE id = :start_id
                    UNION ALL
                    SELECT j.id, j.parent_id FROM jurisdictions j
                    JOIN descendants d ON j.parent_id = d.id
                )
                SELECT id FROM descendants
                """
            )
            res = await db.execute(cte_sql, {"start_id": str(jurisdiction_id)})
            ids = [row[0] for row in res.fetchall()]

            try:
                ids = [UUID(str(i)) for i in ids]
            except Exception:
                pass

            if not ids:
                return None

            update_stmt = (
                update(Jurisdiction)
                .where(Jurisdiction.id.in_(ids))  # type: ignore
                .values(is_deleted=False, deleted_at=None)
            )
            await db.execute(update_stmt)
            await db.commit()

            result = await db.execute(
                select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
            )
            root = result.scalar_one_or_none()
            if not root:
                raise HTTPException(status_code=404, detail="Jurisdiction not found after restore")

            await filter_archived_recursive(root, db)
            return self._serialize_jurisdiction(root)

        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def restore_all_archived_jurisdictions(
        self, db: AsyncSession, project_id: UUID | None = None
    ) -> list[Jurisdiction]:
        """
        Restore all archived jurisdictions and return the restored objects.
        Args:
            db (AsyncSession): Database session.
            project_id (UUID): ID of the Project,
            the jurisdictions are under
            .

        Returns:
            Jurisdictions: The jurisdiction records (archived or active).

        Raises:
            HTTPException: 404 if not found, 500 on DB error.
        """
        try:
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

            ids = [j.id for j in archived_jurisdictions]

            update_stmt = (
                update(Jurisdiction)
                .where(Jurisdiction.id.in_(ids))  # type: ignore
                .values(is_deleted=False, deleted_at=None)
            )

            await db.execute(update_stmt)
            await db.commit()

            for j in archived_jurisdictions:
                try:
                    j.is_deleted = False
                    j.deleted_at = None
                except Exception:
                    pass

            if not isinstance(db, AsyncSession):
                top_level = [
                    j for j in archived_jurisdictions if getattr(j, "parent_id", None) is None
                ]
                nested = []
                for t in top_level:
                    nested.append(self._serialize_jurisdiction(t))
                return nested

            if project_id is not None:
                top_stmt = select(Jurisdiction).where(
                    cast(Any, Jurisdiction.project_id) == project_id,
                    Jurisdiction.parent_id.is_(None),  # type: ignore
                    cast(Any, Jurisdiction.is_deleted).is_(False),
                )
            else:
                top_stmt = select(Jurisdiction).where(
                    Jurisdiction.parent_id.is_(None),  # type: ignore
                    Jurisdiction.id.in_(ids),  # type: ignore
                )

            top_res = await db.execute(top_stmt)
            top_level = top_res.scalars().all()

            nested = []
            for t in top_level:
                await filter_archived_recursive(t, db)
                nested.append(self._serialize_jurisdiction(t))

            return nested

        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_jurisdiction_tree(self, db: AsyncSession, jurisdiction_id: UUID):
        """
        Docstring for get_jurisdiction_tree (nested jurisdiction)

        :param self: Description
        :param db: Description
        :type db: AsyncSession
        :param jurisdiction_id: Description
        :type jurisdiction_id: UUID
        """
        try:
            stmt = (
                select(Jurisdiction)
                .where(Jurisdiction.id == jurisdiction_id)
                .options(
                    selectinload(Jurisdiction.children)  # type: ignore
                )
            )
            result = await db.execute(stmt)
            parent = result.scalars().first()

            if not parent:
                return None

            if getattr(parent, "is_deleted", False):
                try:
                    await db.refresh(parent)
                except Exception:
                    pass

            if getattr(parent, "is_deleted", False):
                return None

            await filter_archived_recursive(parent, db)

            return self._serialize_jurisdiction(parent)

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class OrgResourceGuard:
    """
    Automatically enforces that resources belong to the current user's organization.

    This guard checks resource ownership based on path parameters such as
    `project_id` or `jurisdiction_id`. If a resource belongs to a different
    organization than the current user, it raises an HTTP 403 Forbidden error.

    Router-Level Use Case:
        Apply this guard to an APIRouter to enforce multi-tenant isolation
        across all routes automatically, without calling `verify()` in each route.

    Example:
        from fastapi import APIRouter, Depends

        router = APIRouter(
            prefix="/jurisdictions",
            tags=["Jurisdictions"],
            dependencies=[
                Depends(TenantGuard),
                Depends(OrgResourceGuard)
            ]
        )

        @router.get("/{jurisdiction_id}")
        async def get_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
            # No manual verification required
            jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
            return jurisdiction

    Key Points:
        - Works at the router level: all routes inherit the guard.
        - Automatically resolves project from jurisdiction if needed.
        - Raises 404 if the resource is not found.
        - Raises 403 if a cross-organization access attempt is detected.
    """

    def __init__(self, request: Request, current_user: User = Depends(get_current_user)):
        self.request = request
        self.user = current_user

    async def __call__(self):
        path_params = self.request.path_params

        project_id = path_params.get("project_id")
        jurisdiction_id = path_params.get("jurisdiction_id")

        db: AsyncSession = self.request.state.db

        if jurisdiction_id:
            jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
            if not jurisdiction:
                raise HTTPException(404, "Jurisdiction not found")
            project_id = jurisdiction.project_id

        if project_id:
            project = await db.get(Project, project_id)
            if not project:
                raise HTTPException(404, "Project not found")

            if str(project.org_id) != str(self.user.organization_id):
                raise HTTPException(403, "Cross-organization access denied")
