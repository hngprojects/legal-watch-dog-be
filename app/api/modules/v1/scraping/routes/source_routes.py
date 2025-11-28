"""
API routes for Source CRUD operations.

Provides endpoints for:
- POST /sources - Create new source
- GET /sources - List sources with filtering
- GET /sources/{source_id} - Get single source
- PUT /sources/{source_id} - Update source
- DELETE /sources/{source_id} - Delete source
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.routes.docs.source_routes_docs import (
    create_source_custom_errors,
    create_source_custom_success,
    create_source_responses,
    delete_source_custom_errors,
    delete_source_custom_success,
    delete_source_responses,
    get_source_custom_errors,
    get_source_custom_success,
    get_source_responses,
    get_source_revisions_custom_errors,
    get_source_revisions_custom_success,
    get_source_revisions_responses,
    get_sources_custom_errors,
    get_sources_custom_success,
    get_sources_responses,
    manual_scrape_trigger_custom_errors,
    manual_scrape_trigger_custom_success,
    update_source_custom_errors,
    update_source_custom_success,
    update_source_patch_custom_errors,
    update_source_patch_custom_success,
    update_source_patch_responses,
    update_source_responses,
)
from app.api.modules.v1.scraping.schemas.data_revision_schema import (
    DataRevisionResponse,
    PaginatedRevisions,
    PaginationMetadata,
)
from app.api.modules.v1.scraping.schemas.source_service import (
    SourceCreate,
    SourceUpdate,
)
from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(
    prefix="/sources",
    tags=["Sources"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)
logger = logging.getLogger("app")


@router.post("", status_code=status.HTTP_200_OK, responses=create_source_responses)
async def create_source(
    source_data: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new source for monitoring and scraping.

    Args:
        source_data (SourceCreate): Source creation payload with:
            - jurisdiction_id (uuid.UUID): Parent jurisdiction UUID
            - name (str): Human-readable source name
            - url (HttpUrl): Target URL to scrape
            - source_type (SourceType): Type of source (web, pdf, api)
            - scrape_frequency (str): Scraping frequency (e.g., DAILY, HOURLY)
            - auth_details (Optional[Dict]): Authentication credentials (will be encrypted)
            - scraping_rules (Optional[Dict]): Custom extraction rules
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with created source data.

    Raises:
        HTTPException: 400 if source URL already exists in jurisdiction, 500 if creation fails.

    Examples:
        ```
        POST /sources
        {
            "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Supreme Court Opinions",
            "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
            "source_type": "web",
            "scrape_frequency": "DAILY",
            "scraping_rules": {
                "title_selector": ".opinion-title",
                "content_selector": ".opinion-content",
                "date_selector": ".opinion-date"
            }
        }

        Response (201 Created):
        {
            "status": "success",
            "status_code": 201,
            "message": "Source created successfully",
            "data": {
                "source": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Supreme Court Opinions",
                    "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                    "source_type": "web",
                    "scrape_frequency": "DAILY",
                    "is_active": true,
                    "is_deleted": false,
                    "has_auth": false,
                    "created_at": "2025-11-21T10:30:00"
                }
            }
        }
        ```
    """
    logger.info(f"User {current_user.id} creating source: {source_data.name}")

    service = SourceService()
    source = await service.create_source(db, source_data)

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Source created successfully",
        data={"source": source.model_dump()},
    )


create_source._custom_errors = create_source_custom_errors
create_source._custom_success = create_source_custom_success


@router.get("", status_code=status.HTTP_200_OK, responses=get_sources_responses)
async def get_sources(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    jurisdiction_id: Optional[uuid.UUID] = Query(None, description="Filter by jurisdiction"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a list of sources with optional filtering and pagination.

    By default, soft-deleted sources are excluded from results. To retrieve all sources
    including deleted ones, use a separate query or access the specific source by ID.

    Args:
        skip (int): Pagination offset (default 0).
        limit (int): Maximum records to return (default 100, max 500).
        jurisdiction_id (Optional[uuid.UUID]): Filter by specific jurisdiction.
        is_active (Optional[bool]): Filter by active status (true/false).
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with list of sources and count.


    """
    logger.info(f"User {current_user.id} retrieving sources")

    service = SourceService()
    sources = await service.get_sources(
        db=db,
        skip=skip,
        limit=limit,
        jurisdiction_id=jurisdiction_id,
        is_active=is_active,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Sources retrieved successfully",
        data={
            "sources": [source.model_dump() for source in sources],
            "count": len(sources),
        },
    )


get_sources._custom_errors = get_sources_custom_errors
get_sources._custom_success = get_sources_custom_success


@router.get("/{source_id}", status_code=status.HTTP_200_OK, responses=get_source_responses)
async def get_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a single source by ID (including soft-deleted sources).

    This endpoint allows retrieving a specific source by its ID. It can fetch both
    active and soft-deleted sources, enabling recovery operations or inspection
    of deleted sources.

    Args:
        source_id (uuid.UUID): Source unique identifier.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with source data.

    Raises:
        HTTPException: 404 if source not found.

    """
    logger.info(f"User {current_user.id} retrieving source: {source_id}")

    service = SourceService()
    source = await service.get_source(db, source_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Source retrieved successfully",
        data={"source": source.model_dump()},
    )


get_source._custom_errors = get_source_custom_errors
get_source._custom_success = get_source_custom_success


@router.put("/{source_id}", status_code=status.HTTP_200_OK, responses=update_source_responses)
async def update_source(
    source_id: uuid.UUID,
    source_data: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing source (full or partial update).

    Args:
        source_id (uuid.UUID): Source unique identifier.
        source_data (SourceUpdate): Partial or full update payload. Fields:
            - name (Optional[str]): Update source name
            - url (Optional[HttpUrl]): Update source URL
            - source_type (Optional[SourceType]): Update source type (web, pdf, api)
            - scrape_frequency (Optional[str]): Update scraping frequency
            - is_active (Optional[bool]): Enable/disable source
            - is_deleted (Optional[bool]): Mark as deleted/restored
            - scraping_rules (Optional[Dict]): Update extraction rules
            - auth_details (Optional[Dict]): Update authentication credentials
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with updated source data.

    Raises:
        HTTPException: 404 if source not found, 500 if update fails.

    """
    logger.info(f"User {current_user.id} updating source: {source_id}")

    service = SourceService()
    source = await service.update_source(db, source_id, source_data)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Source updated successfully",
        data={"source": source.model_dump()},
    )


update_source._custom_errors = update_source_custom_errors
update_source._custom_success = update_source_custom_success


@router.delete(
    "/{source_id}", status_code=status.HTTP_204_NO_CONTENT, responses=delete_source_responses
)
async def delete_source(
    source_id: uuid.UUID,
    permanent: bool = Query(
        False, description="Perform permanent hard delete instead of soft delete"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a source - Soft delete by default, permanent delete optional.

    This endpoint supports two deletion modes:
    - **Soft Delete (default)**: Marks source as deleted but keeps it in database.
      Can be restored using PATCH endpoint with `is_deleted: false`.
    - **Hard Delete (permanent=true)**: Permanently removes source from database.
      This action cannot be undone.

    Args:
        source_id (uuid.UUID): Source unique identifier.
        permanent (bool): If true, permanently delete from database (cannot be undone).
                         If false (default), soft delete (can be restored via PATCH).
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        None: 204 No Content on successful deletion.

    Raises:
        HTTPException: 404 if source not found, 500 if deletion fails.

    """
    logger.info(f"User {current_user.id} deleting source: {source_id}, permanent={permanent}")

    service = SourceService()
    await service.delete_source(db, source_id, permanent=permanent)

    return None


delete_source._custom_errors = delete_source_custom_errors
delete_source._custom_success = delete_source_custom_success


@router.patch(
    "/{source_id}", status_code=status.HTTP_200_OK, responses=update_source_patch_responses
)
async def update_source_patch(
    source_id: uuid.UUID,
    source_data: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a source via PATCH - Restore soft-deleted sources or update fields.

    This endpoint allows partial updates to sources. Primary use case is restoring
    soft-deleted sources by setting `is_deleted` to false. Can also update other
    source fields (name, url, scrape_frequency, is_active, scraping_rules, auth_details).

    Args:
        source_id (uuid.UUID): Source unique identifier.
        source_data (SourceUpdate): Partial update payload. Fields:
            - is_deleted (Optional[bool]): Restore deleted source (false) or soft-delete (true)
            - name (Optional[str]): Update source name
            - url (Optional[HttpUrl]): Update source URL
            - source_type (Optional[SourceType]): Update source type (web, pdf, api)
            - scrape_frequency (Optional[str]): Update scraping frequency (e.g., DAILY, HOURLY)
            - is_active (Optional[bool]): Enable/disable source
            - scraping_rules (Optional[Dict]): Update extraction rules
            - auth_details (Optional[Dict]): Update authentication credentials (encrypted)
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with updated source data.

    Raises:
        HTTPException: 404 if source not found, 500 if update fails.

    """
    logger.info(f"User {current_user.id} patching source: {source_id}")

    service = SourceService()
    source = await service.update_source(db, source_id, source_data)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Source updated successfully",
        data={"source": source.model_dump()},
    )


update_source_patch._custom_errors = update_source_patch_custom_errors
update_source_patch._custom_success = update_source_patch_custom_success


@router.get(
    "/{source_id}/revisions",
    status_code=status.HTTP_200_OK,
    responses=get_source_revisions_responses,
)
async def get_source_revisions(
    source_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve revision history for a specific source.

    Returns a paginated list of all data revisions (scrapes) for the given source,
    ordered by most recent first. Each revision includes the extracted data,
    AI summary, timestamp, and change detection flag.

    Args:
        source_id (uuid.UUID): Source unique identifier.
        skip (int): Pagination offset (default 0, min 0).
        limit (int): Maximum records to return (default 50, min 1, max 200).
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with revisions list and pagination metadata.

    Raises:
        HTTPException: 404 if source not found.
    """
    logger.info(
        f"User {current_user.id} retrieving revisions for source {source_id} "
        f"(skip={skip}, limit={limit})"
    )

    service = SourceService()
    revisions, total = await service.get_source_revisions(
        db=db,
        source_id=source_id,
        skip=skip,
        limit=limit,
    )

    # Calculate pagination metadata
    page = (skip // limit) + 1
    pagination_data = calculate_pagination(total=total, page=page, limit=limit)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Revisions retrieved successfully",
        data=PaginatedRevisions(
            revisions=[DataRevisionResponse.model_validate(r) for r in revisions],
            pagination=PaginationMetadata(**pagination_data),
        ).model_dump(),
    )


get_source_revisions._custom_errors = get_source_revisions_custom_errors
get_source_revisions._custom_success = get_source_revisions_custom_success


@router.post("/{source_id}/scrapes", status_code=status.HTTP_200_OK)
async def manual_scrape_trigger(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually triggers a scrape for a specific source.

    WARNING: This runs SYNCHRONOUSLY. The request will wait until
    scraping, AI extraction, and diffing are complete.
    This may cause timeouts if the process takes > 60 seconds.

    Args:
        source_id (UUID): The UUID of the source to scrape

    Returns:
        JSONResponse: Success response with scrape results or error response
    """
    query = select(Source).where(Source.id == source_id)
    result = await db.execute(query)
    source = result.scalars().first()

    if not source:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Source not found",
            error="SOURCE_NOT_FOUND",
        )

    if not source.is_active:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Cannot scrape inactive source. Please enable it first.",
            error="SOURCE_INACTIVE",
        )

    try:
        service = ScraperService(db)
        scrape_result = await service.execute_scrape_job(str(source.id))

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Scrape executed successfully",
            data={"source_id": str(source.id), "status": "COMPLETED", "result": scrape_result},
        )

    except Exception as e:
        logger.error(f"Manual scrape failed for source {source_id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Scrape execution failed",
            error="SCRAPE_EXECUTION_FAILED",
            errors={"details": str(e)},
        )


manual_scrape_trigger._custom_errors = manual_scrape_trigger_custom_errors
manual_scrape_trigger._custom_success = manual_scrape_trigger_custom_success
