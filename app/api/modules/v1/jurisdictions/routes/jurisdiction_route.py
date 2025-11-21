from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
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
from app.api.utils.response_payloads import fail_response, success_response

router = APIRouter(prefix="/jurisdictions", tags=["Jurisdictions"])

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

    try:
        created = await service.create(db, jurisdiction)

        return success_response(
            status_code=201,
            message="Jurisdiction created successfully",
            data={"jurisdiction": created},
        )

    except Exception:
        return fail_response(status_code=400, message="Failed to create jurisdiction")


@router.get("/", status_code=status.HTTP_200_OK, response_model=List[JurisdictionResponseSchema])
async def get_jurisdictions(project_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    """
    Retrieve jurisdictions from the system.

    This endpoint returns a list of jurisdictions, optionally filtered by a specific
    project. If a `project_id` is provided, only jurisdictions belonging to that
    project are returned. If no `project_id` is supplied, all jurisdictions stored
    in the database are returned. Soft-deleted jurisdictions may be excluded
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

    if project_id:
        jurisdictions = await service.get_jurisdictions_by_project(db, project_id)
    else:
        jurisdictions = await service.get_all_jurisdictions(db)

    if not jurisdictions:
        return fail_response(status_code=404, message="No jurisdictions found")

    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": jurisdictions},
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

    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
    if not jurisdiction:
        return fail_response(status_code=404, message="Jurisdiction not found")
    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": jurisdiction},
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
        jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)
        if not jurisdiction:
            return fail_response(status_code=404, message="Jurisdiction not found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(jurisdiction, key, value)

        updated = await service.update(db, jurisdiction)

        return success_response(
            status_code=200,
            message="Jurisdiction updated successfully",
            data={"jurisdiction": updated},
        )

    except Exception:
        return fail_response(status_code=400, message="Failed to update jurisdiction")


@router.delete("/{jurisdiction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Archive (soft delete) a jurisdiction.

    This endpoint marks a jurisdiction as deleted by setting its `is_deleted` flag
    and optionally updating its `deleted_at` timestamp, depending on the underlying
    database logic. The jurisdiction remains in the system for historical reference
    or potential restoration but is treated as inactive or removed in most queries.
    No content is returned in the response.

    Args:
        jurisdiction_id (UUID): The unique identifier of the jurisdiction to archive.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        None: This endpoint returns no response body upon successful deletion.

    Raises:
        HTTPException: If the jurisdiction does not exist, is already archived,
        or if a database error occurs during the archival operation.
    """

    jurisdiction = await service.soft_delete(db, jurisdiction_id)

    if not jurisdiction:
        return fail_response(status_code=404, message="Jurisdiction not found")

    return success_response(
        status_code=200,
        message="Jurisdiction archived successfully",
        data={"jurisdiction_id": str(jurisdiction_id)},
    )


@router.post(
    "/jurisdictions/{id}/restoration",
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

    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id)

    if not jurisdiction or not jurisdiction.is_deleted:
        return fail_response(status_code=404, message="Jurisdiction not found or not deleted")

    jurisdiction.is_deleted = False
    jurisdiction.deleted_at = None
    restored = await service.update(db, jurisdiction)

    return success_response(
        status_code=200,
        message="Jurisdiction restored successfully",
        data={"jurisdiction": restored},
    )
