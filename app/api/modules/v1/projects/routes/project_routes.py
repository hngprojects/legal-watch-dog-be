"""
Project Routes
API endpoints for project management operations.

This module provides RESTful endpoints for project CRUD operations,
including creation, retrieval, updates, archival, and deletion.
All endpoints require authentication and enforce organization-level
access control.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.projects.schemas.project_schema import (
    ProjectBase,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.api.modules.v1.projects.services.project_service import ProjectService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import (
    error_response,
    success_response,
)

router = APIRouter(prefix="/organizations/{organization_id}/projects", tags=["Projects"])
logger = logging.getLogger("app")


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectBase,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project within the authenticated user's organization.

    This endpoint creates a project, associates it with the user's organization,
    and automatically adds the creating user as a member of the project. The project
    is initialized with the provided title, description, and optional master prompt.

    Args:
        payload (ProjectBase):
            The project data containing:
            - **title**: Project title (required, 1-255 characters)
            - **description**: Project description (optional)
            - **master_prompt**: High-level AI prompt for the project (optional)
        current_user (User):
            The authenticated user making the request, automatically injected via
            dependency injection. The user's organization ID is used to associate
            the project.
        db (AsyncSession):
            The database session for executing queries, automatically managed via
            dependency injection.

    Returns:
        JSONResponse: A standardized success response containing:
            - `status`: "success"
            - `message`: "Project created successfully"
            - `data`: Serialized ProjectResponse object with project details

    Raises:
        HTTPException:
            - 401 Unauthorized: If user authentication fails
            - 500 Internal Server Error: If project creation fails due to database errors
    """
    logger.info(f"Creating project for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.create_project(payload, organization_id, current_user.id)

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Project created successfully",
            data=ProjectResponse.model_validate(project).model_dump(),
        )

    except Exception:
        logger.exception(f"Error creating project for user_id={current_user.id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create project. Please try again.",
        )


@router.get(
    "",
    response_model=ProjectListResponse,
)
async def list_projects(
    organization_id: UUID,
    q: Optional[str] = Query(None, description="Search query for project title"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects belonging to the authenticated user's organization.

    This endpoint retrieves a paginated list of projects with optional search
    filtering. Only non-archived projects are returned, and results are sorted
    by creation date in descending order.

    Args:
        q (Optional[str]):
            Search query to filter projects by title (case-insensitive substring match)
        page (int):
            Page number for pagination (default: 1, minimum: 1)
        limit (int):
            Number of items per page (default: 20, range: 1-100)
        current_user (User):
            The authenticated user, used to determine the organization scope
        db (AsyncSession):
            Database session for query execution

    Returns:
        JSONResponse: A success response containing:
            - `status`: "success"
            - `message`: "Projects retrieved successfully"
            - `data`: ProjectListResponse with projects and pagination metadata

    Raises:
        HTTPException:
            - 401 Unauthorized: If user authentication fails
            - 500 Internal Server Error: If project retrieval fails
    """
    logger.info(f"Listing projects for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        result = await project_service.list_projects(organization_id, q=q, page=page, limit=limit)

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
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve projects. Please try again.",
        )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def get_project(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
     Get detailed information about a specific project.

    This endpoint retrieves comprehensive details for a single project,
    including its title, description, master prompt, and metadata. The project
    must belong to the user's organization and must not be archived.

    Args:
        project_id (UUID):
            The unique identifier of the project to retrieve
        current_user (User):
            The authenticated user for organization access verification
        db (AsyncSession):
            Database session for query execution

    Returns:
        JSONResponse: A success response containing:
            - `status`: "success"
            - `message`: "Project retrieved successfully"
            - `data`: ProjectResponse with complete project details

    Raises:
        HTTPException:
            - 401 Unauthorized: If user authentication fails
            - 404 Not Found: If the project doesn't exist or isn't accessible
            - 500 Internal Server Error: If project retrieval fails
    """
    logger.info(f"Getting project_id={project_id} for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.get_project(project_id, organization_id)

        if not project:
            return error_response(
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
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project.",
        )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def update_project(
    project_id: UUID,
    organization_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update project information with partial updates.

    This endpoint supports partial updates to project fields and provides
    archive/restore functionality. Only the fields provided in the request
    will be modified. Archive operations are reversible through restoration.

    Args:
        project_id (UUID):
            The unique identifier of the project to update
        payload (ProjectUpdate):
            The update data containing any combination of:
            - **title**: Updated project title (optional, 1-255 characters)
            - **description**: Updated project description (optional)
            - **master_prompt**: Updated master prompt (optional)
            - **is_deleted**: Boolean to archive (true) or restore (false) the project
        current_user (User):
            The authenticated user for organization access verification
        db (AsyncSession):
            Database session for query execution

    Returns:
        JSONResponse: A success response containing:
            - `status`: "success"
            - `message`: Dynamic message describing the operation outcome
            - `data`: Updated ProjectResponse object

    Raises:
        HTTPException:
            - 401 Unauthorized: If user authentication fails
            - 404 Not Found: If the project doesn't exist or isn't accessible
            - 500 Internal Server Error: If project update fails
    """

    logger.info(f"Updating project_id={project_id} for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.update_project(project_id, organization_id, payload)

        if project is None:
            return error_response(
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
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update project. Please try again.",
        )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a project from the database.

    This endpoint performs a soft deletion of a project by marking it as deleted.
    The project can be restored later using the update endpoint.

    Args:
        project_id (UUID):
            The unique identifier of the project to delete
        current_user (User):
            The authenticated user for organization access verification
        db (AsyncSession):
            Database session for query execution

    Returns:
        Response: HTTP 204 No Content on successful deletion

    Raises:
        HTTPException:
            - 401 Unauthorized: If user authentication fails
            - 403 Forbidden: If user lacks permission for soft deletion
            - 404 Not Found: If the project doesn't exist or isn't accessible
            - 500 Internal Server Error: If project deletion fails
    """
    logger.info(f"Soft deleting project_id={project_id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.soft_delete_project(project_id, organization_id)

        if not project:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project archived successfully",
            data=ProjectResponse.model_validate(project).model_dump(),
        )

    except Exception:
        logger.exception(f"Error during hard delete of project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to permanently delete project.",
        )
