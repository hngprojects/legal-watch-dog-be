"""
Regulatory Source Routes
API endpoints for managing project regulatory sources
"""

import logging
import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.projects.schemas.project_regulatory_source_schema import (
    RegulatorySourceCreate,
    RegulatorySourceResponse,
    RegulatorySourceUpdate,
)
from app.api.modules.v1.projects.services.project_regulatory_source_service import (
    create_regulatory_source,
    delete_regulatory_source,
    get_regulatory_source_by_id,
    list_regulatory_sources,
    update_regulatory_source,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import fail_response, success_response

router = APIRouter(prefix="/regulatory-sources", tags=["Regulatory Sources"])
logger = logging.getLogger(__name__)


# -----------------------------
# CREATE REGULATORY SOURCE
# -----------------------------
@router.post(
    "",
    response_model=RegulatorySourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    payload: RegulatorySourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new regulatory source linked to a project.

    - **project_id**: UUID of the project (required)
    - **value**: URL or content of the regulatory source (required)
    - **source_type**: Type of source (e.g., "website", "PDF")
    """
    logger.info(f"Creating regulatory source for project_id={payload.project_id}")

    try:
        source = await create_regulatory_source(
            db,
            project_id=payload.project_id,
            value=payload.value,
            source_type=payload.source_type,
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Regulatory source created successfully",
            data=RegulatorySourceResponse.model_validate(source).model_dump(),
        )

    except Exception:
        logger.exception(f"Error creating regulatory source for project_id={payload.project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create regulatory source",
            error={
                "errors": {"regulatory_source": ["Failed to create source"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


# -----------------------------
# LIST ALL SOURCES FOR A PROJECT
# -----------------------------
@router.get(
    "",
    response_model=List[RegulatorySourceResponse],
)
async def list_sources(
    project_id: UUID = Query(..., description="Filter by project ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all regulatory sources for a specific project.
    """
    logger.info(f"Listing regulatory sources for project_id={project_id}")

    try:
        sources = await list_regulatory_sources(db, project_id)
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Regulatory sources retrieved successfully",
            data=[RegulatorySourceResponse.model_validate(s).model_dump() for s in sources],
        )

    except Exception:
        logger.exception(f"Error listing regulatory sources for project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list regulatory sources",
            error={
                "errors": {"regulatory_sources": ["Failed to list sources"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


# -----------------------------
# GET A SINGLE SOURCE
# -----------------------------
@router.get(
    "/{source_id}",
    response_model=RegulatorySourceResponse,
)
async def get_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a specific regulatory source by its ID.
    """
    logger.info(f"Fetching regulatory source id={source_id}")

    try:
        source = await get_regulatory_source_by_id(db, source_id)
        if not source:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Regulatory source not found",
                error={
                    "errors": {"regulatory_source": ["Source not found"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Regulatory source retrieved successfully",
            data=RegulatorySourceResponse.model_validate(source).model_dump(),
        )

    except Exception:
        logger.exception(f"Error fetching regulatory source id={source_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch regulatory source",
            error={
                "errors": {"regulatory_source": ["Failed to fetch source"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


# -----------------------------
# UPDATE REGULATORY SOURCE
# -----------------------------
@router.patch(
    "/{source_id}",
    response_model=RegulatorySourceResponse,
)
async def update_source(
    source_id: UUID,
    payload: RegulatorySourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update fields of an existing regulatory source.
    Only provided fields will be updated.
    """
    logger.info(f"Updating regulatory source id={source_id}")

    try:
        source = await update_regulatory_source(
            db,
            source_id,
            value=payload.value,
            source_type=payload.source_type,
            description=payload.description,
        )

        if not source:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Regulatory source not found",
                error={
                    "errors": {"regulatory_source": ["Source not found"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Regulatory source updated successfully",
            data=RegulatorySourceResponse.model_validate(source).model_dump(),
        )

    except Exception:
        logger.exception(f"Error updating regulatory source id={source_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update regulatory source",
            error={
                "errors": {"regulatory_source": ["Failed to update source"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


# -----------------------------
# DELETE REGULATORY SOURCE
# -----------------------------
@router.delete(
    "/{source_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a regulatory source by ID.
    """
    logger.info(f"Deleting regulatory source id={source_id}")

    try:
        deleted = await delete_regulatory_source(db, source_id)
        if not deleted:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Regulatory source not found",
                error={
                    "errors": {"regulatory_source": ["Source not found"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Regulatory source deleted successfully",
            data={"source_id": str(source_id)},
        )

    except Exception:
        logger.exception(f"Error deleting regulatory source id={source_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete regulatory source",
            error={
                "errors": {"regulatory_source": ["Failed to delete source"]},
                "trace_id": str(uuid.uuid4()),
            },
        )
