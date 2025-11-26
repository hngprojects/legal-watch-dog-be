import logging
from datetime import datetime, timezone
from typing import List, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.auth import TenantGuard
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
    JurisdictionResponseSchema,
    JurisdictionUpdateSchema,
)
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import (
    JurisdictionService,
    OrgResourceGuard,
    get_descendant_ids,
)
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/organizations/{organization_id}/jurisdictions",
    tags=["Jurisdictions"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)

service = JurisdictionService()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=JurisdictionResponseSchema)
async def create_jurisdiction(
    payload: JurisdictionCreateSchema, db: AsyncSession = Depends(get_db)
):
    """
    Create a new Jurisdiction within a project.

    This endpoint registers a new jurisdiction entity associated with a specific
    project. It supports hierarchical structures through an optional `parent_id`
    and allows additional metadata such as descriptions, prompts, and scraped data
    to be stored. Timestamps may be provided, but are typically managed by the system.

    Args:
        payload (JurisdictionCreateSchema): The data required to create a new
            jurisdiction. Includes:
                - project_id (UUID): The ID of the project this jurisdiction belongs to.
                - parent_id (Optional[UUID]): Optional reference to a parent jurisdiction,
                allowing nested or hierarchical structures.
                - name (str): The name of the jurisdiction.
                - description (str): A detailed description of the jurisdiction.
                - prompt (Optional[str]): Optional text prompt or instruction content
                associated with the jurisdiction.
                - scrape_output (Optional[Dict[str, Any]]): Optional structured data
                generated from scraping or automated processes.
                - created_at (Optional[datetime]): Optional creation timestamp.
                - updated_at (Optional[datetime]): Optional update timestamp.
                - deleted_at (Optional[datetime]): Optional deletion timestamp.
                - is_deleted (bool): Soft-delete flag (defaults to False).

        db (AsyncSession): Database session dependency for performing persistence operations.

    Returns:
        JurisdictionResponseSchema: The newly created jurisdiction, including its
        generated ID and all persisted fields.

    Raises:
        HTTPException: If the jurisdiction cannot be created due to validation issues,
        a missing parent or project reference, or underlying database errors.
    """

    jurisdiction = Jurisdiction(**payload.model_dump())
    logger.debug("Creating jurisdiction with payload: %s", payload.model_dump())

    try:
        created = await service.create(db, jurisdiction)

        logger.info("Jurisdiction created successfully %s", created)
        return success_response(
            status_code=201,
            message="Jurisdiction created successfully",
            data={"jurisdiction": created},
        )

    except Exception as e:
        logger.exception("Failed to create jurisdiction")
        return error_response(status_code=400, message=f"Failed to create jurisdiction {str(e)}")


@router.get("/", status_code=status.HTTP_200_OK, response_model=List[JurisdictionResponseSchema])
async def get_all_jurisdictions(
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """
    Retrieve jurisdictions from the system with pagination.

    Args:
        db (AsyncSession): Database session used to retrieve jurisdiction records.
        page (int): Page number (1-based).
        page_size (int): Number of items per page.

    Returns:
        List[JurisdictionResponseSchema]: A paginated list of jurisdiction records.
    """

    logger.debug("Fetching jurisdictions from DB (page=%s, page_size=%s)", page, page_size)

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    stmt_total = select(func.count(Jurisdiction.id))  # type: ignore
    result_total = await db.execute(stmt_total)
    total = result_total.scalar() or 0

    if total == 0:
        logger.info("No jurisdictions found")
        return error_response(status_code=404, message="No jurisdictions found")

    stmt_page = select(Jurisdiction).offset((page - 1) * page_size).limit(page_size)
    result_page = await db.execute(stmt_page)
    page_items = result_page.scalars().all()

    pagination = calculate_pagination(total=total, page=page, limit=page_size)

    logger.info("Retrieved %d jurisdictions for page %d", len(page_items), page)

    def _jid(j):
        try:
            return str(j["id"]) if isinstance(j, dict) else str(getattr(j, "id", ""))
        except Exception:
            return ""

    logger.debug("Jurisdiction IDs on page %d: %s", page, [_jid(j) for j in page_items])

    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": page_items, "pagination": pagination},
    )


@router.get(
    "/project/{project_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[JurisdictionResponseSchema],
)
async def get_jurisdictions_by_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """
    Retrieve jurisdictions from the system by project id including pagination.

    Args:
        project_id (UUID): ID of a project to filter jurisdictions by.
        db (AsyncSession): Database session used to retrieve jurisdiction records.
        page (int): Page number (1-based).
        page_size (int): Number of items per page.

    Returns:
        List[JurisdictionResponseSchema]: A paginated list of jurisdiction records.
    """

    jurisdictions = await service.get_jurisdictions_by_project(db, project_id)
    logger.debug("Retrieved %d jurisdictions", len(jurisdictions) if jurisdictions else 0)

    if not jurisdictions:
        logger.info("No jurisdictions found")
        return error_response(status_code=404, message="No jurisdictions found")

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    total = len(jurisdictions)
    pagination = calculate_pagination(total=total, page=page, limit=page_size)

    start = (page - 1) * page_size
    end = start + page_size
    page_items = jurisdictions[start:end]

    logger.info("Retrieved %d jurisdictions for page %d", len(page_items), page)

    def _jid(j):
        try:
            return str(j["id"]) if isinstance(j, dict) else str(getattr(j, "id", ""))
        except Exception:
            return ""

    logger.debug("Jurisdiction IDs on page %d: %s", page, [_jid(j) for j in page_items])

    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": page_items, "pagination": pagination},
    )


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_jurisdictions_by_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete all jurisdictions in a project including
    nested jurisdictions.
    Args:
        project_id
         db (AsyncSession): Database session.
    Return:
           Archived ids
    """
    logger.debug(
        "Soft deleting jurisdictions for project_id=%s. "
        "This will also archive all nested child jurisdictions.",
        project_id,
    )
    deleted = await service.soft_delete(db, project_id=project_id)
    logger.debug("Deleted result: %s", deleted)

    if not deleted:
        logger.info("No jurisdictions found to delete")
        return error_response(status_code=404, message="No jurisdictions found to delete")

    deleted_list = cast(List[Jurisdiction], deleted)
    deleted_ids = [str(j.id) for j in deleted_list]

    logger.info(
        "Archived %d jurisdiction(s) including nested jurisdictions for project_id=%s",
        len(deleted_ids),
        project_id,
    )
    logger.debug(
        "Archived jurisdiction IDs (nested jurisdictions were also archived): %s", deleted_ids
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{jurisdiction_id}",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def get_jurisdiction(
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """
    Retrieve a single jurisdiction by its unique identifier.
    Supports pagination for the jurisdiction's children via `page` and `page_size`.
    """

    logger.debug(
        "Fetching jurisdiction with id=%s (page=%s, page_size=%s)", jurisdiction_id, page, page_size
    )
    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
    if not jurisdiction:
        logger.info("jurisdiction not found: id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found")

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    try:
        if isinstance(jurisdiction, dict):
            children = jurisdiction.get("children") or []
        else:
            children = getattr(jurisdiction, "children", []) or []
    except Exception:
        children = []

    if children is None or not isinstance(children, (list, tuple)):
        children = []

    total_children = len(children)
    pagination = calculate_pagination(total=total_children, page=page, limit=page_size)

    start = (page - 1) * page_size
    end = start + page_size
    page_children = children[start:end]

    try:
        if isinstance(jurisdiction, dict):
            jurisdiction_payload = dict(jurisdiction)
        else:
            jurisdiction_payload = service._serialize_jurisdiction(jurisdiction)
    except Exception:
        jurisdiction_payload = {
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
            "is_deleted": getattr(jurisdiction, "is_deleted", None),
            "children": getattr(jurisdiction, "children", []) or [],
        }

    jurisdiction_payload["children"] = page_children

    logger.info(
        "Jurisdiction retrieved successfully: id=%s, project_id=%s, returned_children=%d/%d",
        jurisdiction_payload.get("id"),
        jurisdiction_payload.get("project_id"),
        len(page_children),
        total_children,
    )
    logger.debug("Jurisdiction details: %s", jurisdiction_payload)

    return success_response(
        status_code=200,
        message="Jurisdiction retrieved successfully",
        data={"jurisdiction": jurisdiction_payload, "pagination": pagination},
    )


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
    """
    Update an existing jurisdiction.

    This endpoint applies partial updates to a jurisdiction identified by its
    `jurisdiction_id`. Only the fields provided in the request payload will be
    updated; all other fields remain unchanged. The update may modify structural
    relationships (such as assigning a new `parent_id`), metadata, descriptive
    content, or soft-deletion status. The `updated_at` timestamp may be supplied
    manually, though many implementations will override it automatically.

    Args:
        jurisdiction_id (UUID): The unique identifier of the jurisdiction to update.
        payload (JurisdictionUpdateSchema): A schema containing the fields to update.
            All fields are optional, enabling partial updates. Fields include:
                - parent_id (Optional[UUID]): Updated parent jurisdiction reference.
                - name (Optional[str]): New name for the jurisdiction.
                - description (Optional[str]): Updated descriptive text.
                - prompt (Optional[str]): Modified prompt or instruction text.
                - scrape_output (Optional[Dict[str, Any]]): Updated structured or scraped data.
                - updated_at (Optional[datetime]): Optional manual update timestamp.
                - is_deleted (Optional[bool]): Allows soft-deleting or restoring the jurisdiction.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        JurisdictionResponseSchema: The updated jurisdiction record with all fields
        persisted and returned in their latest state.

    Raises:
        HTTPException: If the jurisdiction does not exist, if validation fails,
        or if a database error occurs during the update process.
    """

    try:
        logger.debug(
            "Updating jurisdiction id=%s with payload: %s",
            jurisdiction_id,
            payload.model_dump(exclude_unset=True),
        )
        incoming = payload.model_dump(exclude_unset=True)

        if "is_deleted" in incoming and incoming.get("is_deleted") is True:
            logger.debug("Archiving jurisdiction via PATCH: id=%s", jurisdiction_id)
            deleted = await service.soft_delete(db, jurisdiction_id=jurisdiction_id)
            if not deleted:
                logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
                return error_response(status_code=404, message="Jurisdiction not found")

            logger.info(
                "Jurisdiction archived successfully via PATCH: id=%s",
                jurisdiction_id,
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if "is_deleted" in incoming and incoming.get("is_deleted") is False:
            logger.debug("Restoring jurisdiction via PATCH: id=%s", jurisdiction_id)
            restored = await service.restore_jurisdiction_and_children(db, jurisdiction_id)
            if not restored:
                return error_response(
                    status_code=404, message="Jurisdiction not found or not deleted"
                )

            return success_response(
                status_code=200,
                message="Jurisdiction restored successfully",
                data={"jurisdiction": restored},
            )

        jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction:
            logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
            return error_response(status_code=404, message="Jurisdiction not found")

        new_parent_id = incoming.get("parent_id")
        if new_parent_id:
            if new_parent_id == jurisdiction.id:
                error_response(status_code=400, message="Cannot set parent_id to self")

            descendant_ids = await get_descendant_ids(jurisdiction.id, db)
            if new_parent_id in descendant_ids:
                return error_response(
                    status_code=400,
                    message="Cannot set parent_id to a descendant jurisdiction (cycle detected)",
                )

        for key, value in incoming.items():
            setattr(jurisdiction, key, value)

        if "is_deleted" in incoming:
            jurisdiction.deleted_at = (
                datetime.now(timezone.utc) if incoming.get("is_deleted") else None
            )

        updated = await service.update(db, jurisdiction)

        logger.info(
            "Jurisdiction updated successfully: id=%s, project_id=%s",
            updated.id,
            updated.project_id,
        )
        logger.debug("Updated jurisdiction details: %s", updated)
        return success_response(
            status_code=200,
            message="Jurisdiction updated successfully",
            data={"jurisdiction": updated},
        )

    except Exception:
        return error_response(status_code=400, message="Failed to update jurisdiction")


@router.delete("/{jurisdiction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_jurisdiction(
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a single jurisdiction by ID
    whether flat or nested jurisdictions.
    Args:
        jurisdiction_id
        db (AsyncSession): Database session.
    Return:
           Archived ids
    """
    logger.debug("Soft deleting jurisdiction with id=%s", jurisdiction_id)
    deleted = await service.soft_delete(db, jurisdiction_id=jurisdiction_id)
    logger.debug("Deleted result: %s", deleted)

    if not deleted:
        logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found")

    logger.info(
        "Jurisdiction (including nested jurisdiction if any) archived successfully: id=%s",
        jurisdiction_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{jurisdiction_id}/restoration",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def restore_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Restore a previously archived (soft-deleted) jurisdiction
    whether flat or nested.

    This endpoint reverses a soft deletion by setting the jurisdiction’s `is_deleted`
    flag back to `False` and clearing its `deleted_at` timestamp if applicable. It
    returns the fully restored jurisdiction record. If the jurisdiction is not
    currently archived—or does not exist—an appropriate error response is returned.

    Args:
        jurisdiction_id (UUID): The unique identifier of the jurisdiction to restore.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        JurisdictionResponseSchema: The restored jurisdiction with its updated
        deletion status and associated metadata.

    Raises:
        HTTPException: If the jurisdiction does not exist, is not archived,
        or if a database error occurs during the restoration process.
    """
    logger.debug("Attempting to restore jurisdiction with id=%s", jurisdiction_id)

    try:
        restored = await service.restore_jurisdiction_and_children(db, jurisdiction_id)
    except Exception as exc:
        logger.debug(
            "restore_jurisdiction_and_children failed, falling back to legacy restore flow: %s", exc
        )
        try:
            jurisdiction = await service.get_jurisdiction_for_restoration(
                db, jurisdiction_id, restore_nested=True
            )
            if not jurisdiction:
                restored = None
            else:
                try:
                    jurisdiction.is_deleted = False
                    jurisdiction.deleted_at = None
                except Exception:
                    pass
                updated = await service.update(db, jurisdiction)
                if isinstance(updated, dict):
                    restored = updated
                else:
                    try:
                        restored = service._serialize_jurisdiction(updated)
                    except Exception:
                        restored = {
                            "id": getattr(updated, "id", None),
                            "project_id": getattr(updated, "project_id", None),
                            "parent_id": getattr(updated, "parent_id", None),
                            "name": getattr(updated, "name", None),
                            "description": getattr(updated, "description", None),
                            "is_deleted": getattr(updated, "is_deleted", None),
                            "deleted_at": getattr(updated, "deleted_at", None),
                            "children": getattr(updated, "children", [])
                            or updated.__dict__.get("children", []),
                        }
        except Exception as exc2:
            logger.debug("Legacy restore flow failed: %s", exc2)
            restored = None

    if not restored:
        logger.info("Jurisdiction not found or nothing to restore: id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found or not deleted")

    logger.info(
        "Jurisdiction restored successfully: id=%s, project_id=%s",
        restored.get("id"),
        restored.get("project_id"),
    )
    logger.debug("Restored jurisdiction details: %s", restored)
    return success_response(
        status_code=200,
        message="Jurisdiction restored successfully",
        data={"jurisdiction": restored},
    )


@router.post(
    "/project/{project_id}/restoration",
    status_code=status.HTTP_200_OK,
    response_model=List[JurisdictionResponseSchema],
)
async def restore_jurisdictions_by_project_id(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Restore all archived jurisdictions (whether flat or nested)
    for a project and return them.
       Args:
        project_id (UUID): The unique identifier of the project to restore
        all its jurisdiction.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        List[JurisdictionResponseSchema]: List of restored jurisdictions with its updated
        deletion status and associated metadata.

    Raises:
        HTTPException: If the jurisdictions does not exist, are not archived,
        or if a database error occurs during the restoration process.
    """
    logger.debug("Restoring all archived jurisdictions for project_id=%s", project_id)
    restored_jurisdictions = await service.restore_all_archived_jurisdictions(db, project_id)
    logger.debug("Restored result: %s", restored_jurisdictions)

    if not restored_jurisdictions:
        logger.info("No archived jurisdictions found for this project")
        return error_response(
            status_code=404, message="No archived jurisdictions found for this project"
        )

    logger.info(
        "Restored %d jurisdiction(s) successfully for project_id=%s",
        len(restored_jurisdictions),
        project_id,
    )

    def _jid_or_dict(j):
        try:
            return str(j["id"]) if isinstance(j, dict) else str(getattr(j, "id", ""))
        except Exception:
            return ""

    logger.debug("Restored jurisdiction IDs: %s", [_jid_or_dict(j) for j in restored_jurisdictions])
    return success_response(
        status_code=200,
        message=f"Restored {len(restored_jurisdictions)} jurisdiction(s)",
        data={"jurisdictions": restored_jurisdictions},
    )
