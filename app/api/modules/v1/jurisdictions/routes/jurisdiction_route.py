import logging
from datetime import datetime, timezone
from typing import List, cast
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/jurisdictions",
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
async def get_all_jurisdictions(db: AsyncSession = Depends(get_db)):
    """
    Retrieve jurisdictions from the system.

    This endpoint returns a list of jurisdictions in the database.
    Soft-deleted jurisdictions may be excluded
    depending on the implementation of the underlying query logic.

    Args:
        db (AsyncSession): Database session used to retrieve jurisdiction records.

    Returns:
        List[JurisdictionResponseSchema]: A list of all jurisdiction records.
        Each returned jurisdiction includes:
            - id (UUID): Unique identifier of the jurisdiction.
            - project_id (UUID): Identifier of the project it belongs to.
            - parent_id (Optional[UUID]): ID of the parent jurisdiction, if any.
            - name (str): The jurisdiction's name.
            - description (str): Descriptive text explaining the jurisdiction.
            - prompt (Optional[str]): Optional prompt or instruction text.
            - scrape_output (Optional[Dict[str, Any]]): Optional structured data from
            automated processes or scraping.
            - created_at (Optional[datetime]): Timestamp when the jurisdiction was created.
            - updated_at (Optional[datetime]): Timestamp of the last update.
            - deleted_at (Optional[datetime]): Timestamp marking soft deletion, if deleted.
            - is_deleted (bool): Indicates whether the jurisdiction has been soft-deleted.

    Raises:
        HTTPException: If database retrieval fails or invalid parameters are provided.
    """

    logger.debug("Fetching all jurisdictions from DB")
    jurisdictions = await service.get_all_jurisdictions(db)
    logger.debug("Retrieved %d jurisdictions", len(jurisdictions) if jurisdictions else 0)

    if not jurisdictions:
        logger.info("No jurisdictions found")
        return error_response(status_code=404, message="No jurisdictions found")

    logger.info("Retrieved %d jurisdictions successfully", len(jurisdictions))
    logger.debug("Jurisdiction IDs: %s", [str(j.id) for j in jurisdictions])
    return success_response(
        status_code=200,
        message="All Jurisdictions retrieved successfully",
        data={"jurisdictions": jurisdictions},
    )


@router.get(
    "/project/{project_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[JurisdictionResponseSchema],
)
async def get_jurisdictions_by_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Retrieve jurisdictions from the system by project id.

    This endpoint returns a list of jurisdictions by a specific
    project. Soft-deleted jurisdictions may be excluded
    depending on the implementation of the underlying query logic.

    Args:
        project_id (UUID | None): Optional ID of a project to filter jurisdictions by.
            When provided, only jurisdictions linked to this project are returned.
            When omitted, all jurisdictions in the system are returned.
        db (AsyncSession): Database session used to retrieve jurisdiction records.

    Returns:
        List[JurisdictionResponseSchema]: A list of jurisdiction records matching the
        provided filter. Each returned jurisdiction includes:
            - id (UUID): Unique identifier of the jurisdiction.
            - project_id (UUID): Identifier of the project it belongs to.
            - parent_id (Optional[UUID]): ID of the parent jurisdiction, if any.
            - name (str): The jurisdiction's name.
            - description (str): Descriptive text explaining the jurisdiction.
            - prompt (Optional[str]): Optional prompt or instruction text.
            - scrape_output (Optional[Dict[str, Any]]): Optional structured data from
            automated processes or scraping.
            - created_at (Optional[datetime]): Timestamp when the jurisdiction was created.
            - updated_at (Optional[datetime]): Timestamp of the last update.
            - deleted_at (Optional[datetime]): Timestamp marking soft deletion, if deleted.
            - is_deleted (bool): Indicates whether the jurisdiction has been soft-deleted.

    Raises:
        HTTPException: If database retrieval fails or invalid parameters are provided.
    """

    jurisdictions = await service.get_jurisdictions_by_project(db, project_id)
    logger.debug("Retrieved %d jurisdictions", len(jurisdictions) if jurisdictions else 0)

    if not jurisdictions:
        logger.info("No jurisdictions found")
        return error_response(status_code=404, message="No jurisdictions found")

    logger.info("Retrieved %d jurisdictions successfully", len(jurisdictions))
    logger.debug("Jurisdiction IDs: %s", [str(j.id) for j in jurisdictions])

    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": jurisdictions},
    )


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_jurisdictions_by_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete all jurisdictions in a project.
    Args:
        project_id
         db (AsyncSession): Database session.
    Return:
           Archived ids
    """
    logger.debug("Soft deleting jurisdictions for project_id=%s", project_id)
    deleted = await service.soft_delete(db, project_id=project_id)
    logger.debug("Deleted result: %s", deleted)

    if not deleted:
        logger.info("No jurisdictions found to delete")
        return error_response(status_code=404, message="No jurisdictions found to delete")

    deleted_list = cast(List[Jurisdiction], deleted)
    deleted_ids = [str(j.id) for j in deleted_list]

    logger.info(
        "Archived %d jurisdiction(s) successfully for project_id=%s", len(deleted_ids), project_id
    )
    logger.debug("Archived jurisdiction IDs: %s", deleted_ids)
    return success_response(
        status_code=204,
        message=f"{len(deleted_ids)} Jurisdiction(s) archived successfully",
    )


@router.get(
    "/{jurisdiction_id}",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def get_jurisdiction(jurisdiction_id, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a single jurisdiction by its unique identifier.

    This endpoint returns the full details of a specific jurisdiction if it exists
    in the system. The jurisdiction is looked up by its `jurisdiction_id`, and the
    response includes all metadata and structural information about the record.
    If the jurisdiction does not exist—or has been soft-deleted depending on the
    query behavior—an appropriate error is returned.

    Args:
        jurisdiction_id (UUID): The unique identifier of the jurisdiction to retrieve.
        db (AsyncSession): Database session used to perform the lookup.

    Returns:
        JurisdictionResponseSchema: A detailed representation of the jurisdiction,
        including:
            - id (UUID): Unique ID of the jurisdiction.
            - project_id (UUID): ID of the project it belongs to.
            - parent_id (Optional[UUID]): Optional parent jurisdiction.
            - name (str): The jurisdiction's name.
            - description (str): Text describing the jurisdiction.
            - prompt (Optional[str]): Optional prompt or instruction text.
            - scrape_output (Optional[Dict[str, Any]]): Structured data generated by
              automated or scraping processes.
            - created_at (Optional[datetime]): Timestamp of creation.
            - updated_at (Optional[datetime]): Timestamp of last update.
            - deleted_at (Optional[datetime]): Timestamp of deletion if soft-deleted.
            - is_deleted (bool): Whether the jurisdiction is soft-deleted.

    Raises:
        HTTPException: If the jurisdiction does not exist, is unavailable, or if a
        database error occurs during retrieval.
    """

    logger.debug("Fetching jurisdiction with id=%s", jurisdiction_id)
    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
    if not jurisdiction:
        logger.info("jurisdiction not found")
        return error_response(status_code=404, message="Jurisdiction not found")

    logger.info(
        "Jurisdiction retrieved successfully: id=%s, project_id=%s",
        jurisdiction.id,
        jurisdiction.project_id,
    )
    logger.debug("Jurisdiction details: %s", jurisdiction)
    return success_response(
        status_code=200,
        message="Jurisdiction retrieved successfully",
        data={"Jurisdiction": jurisdiction},
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
        jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
        if not jurisdiction:
            logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
            return error_response(status_code=404, message="Jurisdiction not found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(jurisdiction, key, value)

        if "is_deleted" in payload.model_dump(exclude_unset=True):
            if payload.is_deleted:
                jurisdiction.deleted_at = datetime.now(timezone.utc)
            else:
                jurisdiction.deleted_at = None

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
    Soft delete a single jurisdiction by ID.
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

    # deleted_jurisdiction = cast(Jurisdiction, deleted)

    logger.info("Jurisdiction archived successfully: id=%s", jurisdiction_id)
    return success_response(
        status_code=204,
        message="Jurisdiction archived successfully",
    )


@router.post(
    "/{jurisdiction_id}/restoration",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
)
async def restore_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Restore a previously archived (soft-deleted) jurisdiction.

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
    jurisdiction = await service.get_jurisdiction_for_restoration(db, jurisdiction_id)

    if not jurisdiction or not jurisdiction.is_deleted:
        logger.info("Jurisdiction not found or not deleted: id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found or not deleted")

    jurisdiction.is_deleted = False
    jurisdiction.deleted_at = None
    restored = await service.update(db, jurisdiction)

    logger.info(
        "Jurisdiction restored successfully: id=%s, project_id=%s",
        restored.id,
        restored.project_id,
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
async def restore_jurisdictions(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Restore all archived jurisdictions for a project and return them.
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
    logger.debug("Restored jurisdiction IDs: %s", [str(j.id) for j in restored_jurisdictions])
    return success_response(
        status_code=200,
        message=f"Restored {len(restored_jurisdictions)} jurisdiction(s)",
        data={"jurisdictions": restored_jurisdictions},
    )
