"""
Project Routes
API endpoints for project management
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.projects.schemas.project_schema import (
    ProjectBase,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.api.modules.v1.projects.services.project_service import (
    create_project_service,
    get_project_service,
    hard_delete_project_service,
    list_projects_service,
    restore_project_service,
    soft_delete_project_service,
    update_project_service,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import (
    fail_response,
    success_response,
)

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = logging.getLogger("app")


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectBase,
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
            data=ProjectResponse.model_validate(project).model_dump(),
        )

    except Exception:
        logger.exception(f"Error creating project for user_id={current_user.id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create project. Please try again.",
        )


@router.get(
    "",
    response_model=ProjectListResponse,
)
async def list_projects(
    q: Optional[str] = Query(None, description="Search query for project title"),
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
            db, current_user.organization_id, q=q, page=page, limit=limit
        )

        projects_list = [ProjectResponse.model_validate(p).model_dump() for p in result["data"]]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Projects retrieved successfully",
            data=ProjectListResponse(
                projects=projects_list,
                total=result["total"],
                page=result["page"],
                limit=result["limit"],
                total_pages=result["total_pages"],
            ).model_dump(),
        )

    except Exception:
        logger.exception(f"Error listing projects for user_id={current_user.id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve projects. Please try again.",
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
        project = await get_project_service(db, project_id, current_user.organization_id)

        if not project:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
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
            message="Failed to retrieve project.",
        )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
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
                message="Project not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project updated successfully",
            data=ProjectResponse.model_validate(project).model_dump(),
        )

    except Exception:
        logger.exception(f"Error updating project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update project. Please try again.",
        )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a project. This removes the project from
    active listings but preserves historical data for audit purposes.
    """
    logger.info(f"Deleting project_id={project_id} for user_id={current_user.id}")

    try:
        deleted = await soft_delete_project_service(db, project_id, current_user.organization_id)

        if not deleted:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception:
        logger.exception(f"Error deleting project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete project. Please try again.",
        )


@router.post(
    "/{project_id}/undo-delete",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
)
async def restore_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore a soft-deleted project.
    """
    logger.info(f"Restoring project_id={project_id}")

    try:
        restored = await restore_project_service(db, project_id, current_user.organization_id)

        if not restored:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found or not deleted",
            )

        project = await get_project_service(db, project_id, current_user.organization_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project restored successfully",
            data=ProjectResponse.model_validate(project),
        )

    except Exception:
        logger.exception(f"Error restoring project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to restore project. Please try again.",
        )


@router.delete(
    "/{project_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def hard_delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a project (irreversible).
    This completely removes the project and all related data from the database.
    Use with extreme caution!

    Requires admin privileges or special confirmation.
    """
    logger.info(f"hard deleting project_id={project_id}")

    try:
        deleted = await hard_delete_project_service(db, project_id, current_user.organization_id)

        if not deleted:
            return fail_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception:
        logger.exception(f"Error during hard delete of project_id={project_id}")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to permanently delete project.",
        )
