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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.scraping.schemas.source_service import (
    SourceCreate,
    SourceUpdate,
)
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

router = APIRouter(prefix="/sources", tags=["Sources"])
logger = logging.getLogger("app")


@router.post("", status_code=201)
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
        HTTPException: 400 if URL already exists, 500 if creation fails.

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
        status_code=201,
        message="Source created successfully",
        data={"source": source.model_dump()},
    )


@router.get("", status_code=200)
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

    Examples:
        ```
        GET /sources?jurisdiction_id=550e8400-e29b-41d4-a716-446655440000&is_active=true

        Response (200 OK):
        {
            "status": "success",
            "status_code": 200,
            "message": "Sources retrieved successfully",
            "data": {
                "sources": [
                    {
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
                ],
                "count": 1
            }
        }
        ```
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
        status_code=200,
        message="Sources retrieved successfully",
        data={
            "sources": [source.model_dump() for source in sources],
            "count": len(sources),
        },
    )


@router.get("/{source_id}", status_code=200)
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

    Examples:
        ```
        GET /sources/123e4567-e89b-12d3-a456-426614174000

        Response (200 OK):
        {
            "status": "success",
            "status_code": 200,
            "message": "Source retrieved successfully",
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
    logger.info(f"User {current_user.id} retrieving source: {source_id}")

    service = SourceService()
    source = await service.get_source(db, source_id)

    return success_response(
        status_code=200,
        message="Source retrieved successfully",
        data={"source": source.model_dump()},
    )


@router.put("/{source_id}", status_code=200)
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

    Examples:
        ```
        PUT /sources/123e4567-e89b-12d3-a456-426614174000
        {
            "scrape_frequency": "HOURLY",
            "is_active": false
        }

        Response (200 OK):
        {
            "status": "success",
            "status_code": 200,
            "message": "Source updated successfully",
            "data": {
                "source": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Supreme Court Opinions",
                    "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                    "source_type": "web",
                    "scrape_frequency": "HOURLY",
                    "is_active": false,
                    "is_deleted": false,
                    "has_auth": false,
                    "created_at": "2025-11-21T10:30:00"
                }
            }
        }
        ```
    """
    logger.info(f"User {current_user.id} updating source: {source_id}")

    service = SourceService()
    source = await service.update_source(db, source_id, source_data)

    return success_response(
        status_code=200,
        message="Source updated successfully",
        data={"source": source.model_dump()},
    )


@router.delete("/{source_id}", status_code=204)
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

    Examples:
        **Soft Delete (Recoverable):**
        ```
        DELETE /sources/123e4567-e89b-12d3-a456-426614174000

        Response: 204 No Content (empty body)

        After soft delete:
        - Source marked as deleted (is_deleted = true)
        - Not returned in GET /sources list
        - Can be restored via: PATCH /sources/{id} with {"is_deleted": false}
        ```

        **Hard Delete (Permanent):**
        ```
        DELETE /sources/123e4567-e89b-12d3-a456-426614174000?permanent=true

        Response: 204 No Content (empty body)

        After hard delete:
        - Source permanently removed from database
        - Cannot be recovered
        - GET /sources/{id} will return 404
        ```
    """
    logger.info(f"User {current_user.id} deleting source: {source_id}, permanent={permanent}")

    service = SourceService()
    await service.delete_source(db, source_id, permanent=permanent)

    # 204 No Content response
    return None


@router.patch("/{source_id}", status_code=200)
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

    Examples:
        **Restore Soft-Deleted Source:**
        ```
        PATCH /sources/123e4567-e89b-12d3-a456-426614174000
        {
            "is_deleted": false
        }

        Response (200 OK):
        {
            "status": "success",
            "status_code": 200,
            "message": "Source updated successfully",
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

        **Update Multiple Fields:**
        ```
        PATCH /sources/123e4567-e89b-12d3-a456-426614174000
        {
            "is_deleted": false,
            "scrape_frequency": "HOURLY",
            "is_active": true
        }

        Response (200 OK): Same structure as above
        ```
    """
    logger.info(f"User {current_user.id} patching source: {source_id}")

    service = SourceService()
    source = await service.update_source(db, source_id, source_data)

    return success_response(
        status_code=200,
        message="Source updated successfully",
        data={"source": source.model_dump()},
    )
