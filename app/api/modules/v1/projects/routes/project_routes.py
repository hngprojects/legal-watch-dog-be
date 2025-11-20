"""
Project Routes
API endpoints for project management
"""

import logging
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.middleware.get_current_user import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.projects.schemas.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.api.modules.v1.projects.services.project_service import (
    create_project_service,
    delete_project_service,
    get_project_service,
    list_projects_service,
    update_project_service,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import fail_response, success_response

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project within the authenticated user's organization.
    The creating user is automatically added to the project.

    - **title**: Project title (required, max 255 characters)
    - **description**: Project description (required)
    """
    logger.info(f"Creating project for user_id={current_user.id}")

    try:
        project = await create_project_service(
            db, payload, current_user.organization_id, current_user.id
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Project created successfully",
            data=ProjectResponse.model_validate(project),
        )

    except Exception:
        logger.exception(f"Error creating project for user_id={current_user.id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create project. Please try again.",
            data={
                "errors": {"project": ["Failed to create project"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


@router.get(
    "",
    response_model=ProjectListResponse,
)
async def list_projects(
    q: Optional[str] = Query(None, description="Search query for project title"),
    owner: Optional[UUID] = Query(
        None, description="Filter by project owner/creator user ID"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects belonging to the authenticated user's organization
    with optional filtering and pagination.

    - **q**: Search projects by title (case-insensitive)
    - **owner**: Filter by user ID who created/owns the project
    - **page**: Page number (default: 1)
    - **limit**: Results per page (default: 20, max: 100)
    """
    logger.info(f"Listing projects for user_id={current_user.id}")

    try:
        result = await list_projects_service(
            db, current_user.organization_id, q=q, owner=owner, page=page, limit=limit
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Projects retrieved successfully",
            data=ProjectListResponse(
                data=[ProjectResponse.model_validate(p) for p in result["data"]],
                total=result["total"],
                page=result["page"],
                limit=result["limit"],
                total_pages=result["total_pages"],
            ),
        )

    except Exception:
        logger.exception(f"Error listing projects for user_id={current_user.id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve projects. Please try again.",
            data={
                "errors": {"projects": ["Failed to retrieve projects"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific project including
    title, description, master prompt, and metadata.
    """
    logger.info(f"Getting project_id={project_id} for user_id={current_user.id}")

    try:
        project = await get_project_service(
            db, project_id, current_user.organization_id
        )

        if not project:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found or you don't have access to it",
                data={
                    "errors": {"project": ["Project not found"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project retrieved successfully",
            data=ProjectResponse.model_validate(project),
        )

    except Exception:
        logger.exception(f"Error getting project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project. Please try again.",
            data={
                "errors": {"project": ["Failed to retrieve project"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update project information. Only provided fields will be updated.

    - **title**: Updated project title (optional)
    - **description**: Updated project description (optional)
    """
    logger.info(f"Updating project_id={project_id} for user_id={current_user.id}")

    try:
        project = await update_project_service(
            db, project_id, current_user.organization_id, payload
        )

        if not project:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found or you don't have access to it",
                data={
                    "errors": {"project": ["Project not found"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project updated successfully",
            data=ProjectResponse.model_validate(project),
        )

    except Exception:
        logger.exception(f"Error updating project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update project. Please try again.",
            data={
                "errors": {"project": ["Failed to update project"]},
                "trace_id": str(uuid.uuid4()),
            },
        )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Archive or soft-delete a project. This removes the project from
    active listings but preserves historical data for audit purposes.
    """
    logger.info(f"Deleting project_id={project_id} for user_id={current_user.id}")

    try:
        deleted = await delete_project_service(
            db, project_id, current_user.organization_id
        )

        if not deleted:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found or you don't have access to it",
                data={
                    "errors": {"project": ["Project not found"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project deleted successfully",
            data={"project_id": str(project_id)},
        )

    except Exception:
        logger.exception(f"Error deleting project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete project. Please try again.",
            data={
                "errors": {"project": ["Failed to delete project"]},
                "trace_id": str(uuid.uuid4()),
            },
        )
