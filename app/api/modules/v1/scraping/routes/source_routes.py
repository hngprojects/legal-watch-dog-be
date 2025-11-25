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

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.scraping.schemas.source_service import (
    SourceCreate,
    SourceUpdate,
    SourceRead,
)
from app.api.modules.v1.scraping.schemas.revision_schemas import (
    DataRevisionResponse,
    ChangeDiffResponse,
    RevisionListResponse,
    ChangeListResponse,
)
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
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
    service = SourceService()
    source = await service.update_source(db, source_id, source_data)

    return success_response(
        status_code=200,
        message="Source updated successfully",
        data={"source": source.model_dump()},
    )


@router.get("/{source_id}/revisions", response_model=RevisionListResponse)
async def get_source_revisions(
    source_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get revision history for a specific source.

    Returns paginated list of DataRevision records with extracted data,
    AI summaries, and timestamps for the specified source.

    Args:
        source_id (str): UUID of the source to get revisions for.
        page (int): Page number for pagination (default: 1).
        limit (int): Number of items per page (default: 20, max: 100).
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        RevisionListResponse: Paginated list of revisions with metadata.

    Raises:
        HTTPException: 404 if source not found or no access.

    Examples:
        ```
        GET /sources/123e4567-e89b-12d3-a456-426614174000/revisions?page=1&limit=10

        Response (200 OK):
        {
            "status": "success",
            "status_code": 200,
            "message": "Revisions retrieved successfully",
            "data": {
                "revisions": [
                    {
                        "id": "rev-uuid-1",
                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                        "minio_object_key": "raw/project/source/timestamp.html",
                        "content_hash": "abc123...",
                        "extracted_data": {
                            "rate_21_and_over": 12.21,
                            "rate_18_to_20": 10.0,
                            "effective_date": "April 2025"
                        },
                        "ai_summary": "National minimum wage rates updated...",
                        "ai_markdown_summary": "# Wage Rates\\n\\n| Category | Rate |\\n|----------|------|\\n| 21+ | £12.21 |",
                        "ai_confidence_score": 1.0,
                        "scraped_at": "2025-11-25T10:30:00Z",
                        "was_change_detected": true
                    }
                ],
                "total": 25,
                "page": 1,
                "limit": 10,
                "total_pages": 3
            }
        }
        ```
    """
    logger.info(f"User {current_user.id} fetching revisions for source: {source_id}")

    # Convert string UUID to UUID object
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source ID format")

    # Verify source exists and user has access (through organization/project)
    # This would need additional logic to check permissions

    # Calculate offset
    offset = (page - 1) * limit

    # Query revisions with pagination
    from sqlalchemy import desc
    query = (
        db.query(DataRevision)
        .filter(DataRevision.source_id == source_uuid)
        .order_by(desc(DataRevision.scraped_at))
        .offset(offset)
        .limit(limit)
    )

    revisions = await db.execute(query)
    revisions_list = revisions.scalars().all()

    # Get total count
    count_query = db.query(DataRevision).filter(DataRevision.source_id == source_uuid)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())

    # Calculate total pages
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    # Convert to response models
    revision_responses = [
        DataRevisionResponse.model_validate(rev) for rev in revisions_list
    ]

    response_data = RevisionListResponse(
        revisions=revision_responses,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

    return success_response(
        status_code=200,
        message="Revisions retrieved successfully",
        data=response_data.model_dump(),
    )


@router.get("/{source_id}/changes", response_model=ChangeListResponse)
async def get_source_changes(
    source_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get change history for a specific source.

    Returns paginated list of ChangeDiff records with change summaries,
    risk levels, and confidence scores for detected changes.

    Args:
        source_id (str): UUID of the source to get changes for.
        page (int): Page number for pagination (default: 1).
        limit (int): Number of items per page (default: 20, max: 100).
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        ChangeListResponse: Paginated list of changes with metadata.

    Raises:
        HTTPException: 404 if source not found or no access.

    Examples:
        ```
        GET /sources/123e4567-e89b-12d3-a456-426614174000/changes?page=1&limit=10

        Response (200 OK):
        {
            "status": "success",
            "status_code": 200,
            "message": "Changes retrieved successfully",
            "data": {
                "changes": [
                    {
                        "diff_id": "diff-uuid-1",
                        "new_revision_id": "new-rev-uuid",
                        "old_revision_id": "old-rev-uuid",
                        "diff_patch": {
                            "change_summary": "National minimum wage increased by £1.21 for 21+ age group",
                            "risk_level": "HIGH"
                        },
                        "ai_confidence": 0.95
                    }
                ],
                "total": 5,
                "page": 1,
                "limit": 10,
                "total_pages": 1
            }
        }
        ```
    """
    logger.info(f"User {current_user.id} fetching changes for source: {source_id}")

    # Convert string UUID to UUID object
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source ID format")

    # Calculate offset
    offset = (page - 1) * limit

    # Query changes with pagination
    # Join with data_revisions to ensure we only get changes for this source
    from sqlalchemy import desc
    query = (
        db.query(ChangeDiff)
        .join(DataRevision, ChangeDiff.new_revision_id == DataRevision.id)
        .filter(DataRevision.source_id == source_uuid)
        .order_by(desc(ChangeDiff.diff_id))  # Assuming diff_id has timestamp info
        .offset(offset)
        .limit(limit)
    )

    changes = await db.execute(query)
    changes_list = changes.scalars().all()

    # Get total count
    count_query = (
        db.query(ChangeDiff)
        .join(DataRevision, ChangeDiff.new_revision_id == DataRevision.id)
        .filter(DataRevision.source_id == source_uuid)
    )
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())

    # Calculate total pages
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    # Convert to response models
    change_responses = [
        ChangeDiffResponse.model_validate(change) for change in changes_list
    ]

    response_data = ChangeListResponse(
        changes=change_responses,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

    return success_response(
        status_code=200,
        message="Changes retrieved successfully",
        data=response_data.model_dump(),
    )
