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
from app.api.modules.v1.scraping.schemas.scrape import (
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
    Create a new source.

    Args:
        source_data (SourceCreate): Source creation payload.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with created source data.

    Raises:
        HTTPException: 500 if creation fails.

    Examples:
        POST /sources
        {
            "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Ministry of Justice",
            "url": "https://justice.gov.example",
            "source_type": "web",
            "scrape_frequency": "DAILY",
            "auth_details": {"username": "user", "password": "pass"}
        }

        Response:
        {
            "status": "success",
            "status_code": 201,
            "message": "Source created successfully",
            "data": { ... }
        }
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
    Retrieve a list of sources with optional filtering.

    Args:
        skip (int): Pagination offset.
        limit (int): Maximum number of results.
        jurisdiction_id (Optional[uuid.UUID]): Filter by jurisdiction.
        is_active (Optional[bool]): Filter by active status.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with list of sources.

    Examples:
        GET /sources?jurisdiction_id=123e4567-e89b-12d3-a456-426614174000&is_active=true

        Response:
        {
            "status": "success",
            "status_code": 200,
            "message": "Sources retrieved successfully",
            "data": {
                "sources": [...],
                "count": 5
            }
        }
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
    Retrieve a single source by ID.

    Args:
        source_id (uuid.UUID): Source unique identifier.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with source data.

    Raises:
        HTTPException: 404 if source not found.

    Examples:
        GET /sources/123e4567-e89b-12d3-a456-426614174000

        Response:
        {
            "status": "success",
            "status_code": 200,
            "message": "Source retrieved successfully",
            "data": { ... }
        }
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
    Update an existing source.

    Args:
        source_id (uuid.UUID): Source unique identifier.
        source_data (SourceUpdate): Partial or full update payload.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with updated source data.

    Raises:
        HTTPException: 404 if source not found, 500 if update fails.

    Examples:
        PUT /sources/123e4567-e89b-12d3-a456-426614174000
        {
            "scrape_frequency": "HOURLY",
            "is_active": false
        }

        Response:
        {
            "status": "success",
            "status_code": 200,
            "message": "Source updated successfully",
            "data": { ... }
        }
    """
    logger.info(f"User {current_user.id} updating source: {source_id}")

    service = SourceService()
    source = await service.update_source(db, source_id, source_data)

    return success_response(
        status_code=200,
        message="Source updated successfully",
        data={"source": source.model_dump()},
    )


@router.delete("/{source_id}", status_code=200)
async def delete_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a source by ID.

    Args:
        source_id (uuid.UUID): Source unique identifier.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Standard success response with deletion confirmation.

    Raises:
        HTTPException: 404 if source not found, 500 if deletion fails.

    Examples:
        DELETE /sources/123e4567-e89b-12d3-a456-426614174000

        Response:
        {
            "status": "success",
            "status_code": 200,
            "message": "Source deleted successfully",
            "data": {
                "message": "Source successfully deleted",
                "source_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    """
    logger.info(f"User {current_user.id} deleting source: {source_id}")

    service = SourceService()
    result = await service.delete_source(db, source_id)

    return success_response(
        status_code=200,
        message="Source deleted successfully",
        data=result,
    )
