"""
Project Services
Business logic for project operations with proper database integration
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import and_, func, select

from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.projects.schemas.project_schema import (
    ProjectBase,
    ProjectUpdate,
)
from app.api.modules.v1.projects.utils.project_utils import (
    calculate_pagination,
    check_project_user_exists,
    get_project_by_id,
    get_project_by_id_including_deleted,
    get_user_by_id,
)

logger = logging.getLogger("app")


async def create_project_service(
    db: AsyncSession,
    data: ProjectBase,
    organization_id: UUID,
    user_id: UUID,
) -> Project:
    """
    Create a new project and add creator as member.

    Args:
        db: Database session
        data: Project creation data
        organization_id: Organization UUID
        user_id: User UUID of user

    Returns:
        Created Project object
    """
    logger.info(
        f"Creating project '{data.title}' for organization_id={organization_id}, user_id={user_id}"
    )

    project = Project(
        title=data.title,
        description=data.description,
        master_prompt=data.master_prompt,
        org_id=organization_id,
    )

    db.add(project)
    await db.commit()
    db.refresh(project)

    logger.info(f"Created project with id={project.id}")

    return project


async def list_projects_service(
    db: AsyncSession,
    organization_id: UUID,
    q: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """
    List projects with filtering and pagination.

    Args:
        db: Database session
        organization_id: Organization UUID
        q: Search query for title
        owner: Filter by owner user ID
        page: Page number
        limit: Items per page

    Returns:
        Dictionary with projects list and pagination metadata
    """
    logger.info(
        f"Listing projects for organization_id={organization_id}, q={q}, page={page}, limit={limit}"
    )

    statement = select(Project).where(
        and_(Project.org_id == organization_id, Project.is_deleted.is_(False))
    )
    logger.info(f"Base SQL: {str(statement)}")
    if q:
        statement = statement.where(Project.title.ilike(f"%{q}%"))
        logger.info(f"Applied search filter: q={q}")

    count_statement = select(func.count()).select_from(statement.subquery())
    total_result = await db.execute(count_statement)
    # ScalarResult from db.exec(); use one() to retrieve the single scalar count
    total = total_result.scalar_one()

    logger.info(f"Found {total} projects matching criteria")

    offset = (page - 1) * limit
    statement = statement.offset(offset).limit(limit).order_by(Project.created_at.desc())
    result = await db.execute(statement)
    projects = result.scalars().all()

    pagination = calculate_pagination(total, page, limit)

    return {"data": projects, **pagination}


async def get_project_service(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> Optional[Project]:
    """
    Get project by ID with access verification.

    Args:
        db: Database session
        project_id: Project UUID
        organization_id: Organization UUID

    Returns:
        Project object if found and accessible, None otherwise
    """
    logger.info(f"Fetching project_id={project_id} for organization_id={organization_id}")

    project = await get_project_by_id(db, project_id, organization_id)

    if project:
        logger.info(f"Project found: {project.title}")
    else:
        logger.warning(f"Project not found or no access: project_id={project_id}")

    return project


async def update_project_service(
    db: AsyncSession,
    project_id: UUID,
    organization_id: UUID,
    data: ProjectUpdate,
) -> Optional[Project]:
    """
    Update project with provided data.

    Args:
        db: Database session
        project_id: Project UUID
        organization_id: Organization UUID
        data: Update data

    Returns:
        Updated Project object if found, None otherwise
    """
    logger.info(f"Updating project_id={project_id}")

    project = await get_project_by_id(db, project_id, organization_id)

    if not project:
        logger.warning(f"Project not found for update: project_id={project_id}")
        return None

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(project, field, value)
        logger.info(f"Updated field '{field}' for project_id={project_id}")

    project.updated_at = datetime.now(timezone.utc)

    db.add(project)
    await db.commit()
    await db.refresh(project)

    logger.info(f"Project updated successfully: project_id={project_id}")

    return project


async def soft_delete_project_service(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> bool:
    """
    soft delete/archive project.

    Args:
        db: Database session
        project_id: Project UUID
        organization_id: Organization UUID

    Returns:
        True if soft deleted, False if not found
    """
    logger.info(f"soft deleting project_id={project_id}")

    project = await get_project_by_id(db, project_id, organization_id)

    if not project:
        logger.warning(f"Project not found for deletion: project_id={project_id}")
        return False

    if project.is_deleted:
        logger.warning(f"Project already deleted: project_id={project_id}")
        return False

    project.is_deleted = True
    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)

    logger.info(f"Project soft deleted successfully: project_id={project_id}")

    return True


async def restore_project_service(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> bool:
    """
    Restore a soft-deleted project.
    """
    logger.info(f"Restoring project_id={project_id}")

    project = await get_project_by_id_including_deleted(db, project_id, organization_id)

    if not project:
        logger.warning(f"Project not found: project_id={project_id}")
        return False

    if not project.is_deleted:
        logger.warning(f"Project not deleted: project_id={project_id}")
        return False

    project.is_deleted = False
    project.deleted_at = None
    project.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(project)

    logger.info(f"Project restored successfully: project_id={project_id}")

    return True


async def hard_delete_project_service(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> bool:
    """
    Permanently delete project from database (irreversible), also includes soft deleted projects.

    Args:
        db: Database session
        project_id: Project UUID
        organization_id: Organization UUID

    Returns:
        True if deleted, False if not found
    """
    logger.warning(f"hard deleting project_id={project_id}")

    project = await get_project_by_id_including_deleted(db, project_id, organization_id)

    if not project:
        logger.warning(f"Project not found for hard delete: project_id={project_id}")
        return False

    await db.delete(project)
    await db.commit()

    logger.warning(f"Project deleted permanently: project_id={project_id}")

    return True


async def get_project_users_service(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> Optional[List[UUID]]:
    """
    Get list of user IDs in project.

    Args:
        db: Database session
        project_id: Project UUID
        organization_id: Organization UUID

    Returns:
        List of user UUIDs if project exists, None otherwise
    """
    logger.info(f"Fetching users for project_id={project_id}")

    project = await get_project_by_id(db, project_id, organization_id)
    if not project:
        logger.warning(f"Project not found: project_id={project_id}")
        return None

    statement = select(ProjectUser.user_id).where(ProjectUser.project_id == project_id)
    result = await db.execute(statement)
    user_ids = result.all()

    logger.info(f"Found {len(user_ids)} users in project_id={project_id}")

    return list(user_ids)


async def add_user_to_project_service(
    db: AsyncSession, project_id: UUID, user_id: UUID, organization_id: UUID
) -> tuple[bool, str]:
    """
    Add user to project.

    Args:
        db: Database session
        project_id: Project UUID
        user_id: User UUID to add
        organization_id: Organization UUID

    Returns:
        Tuple of (success: bool, message: str)
    """
    logger.info(f"Adding user_id={user_id} to project_id={project_id}")

    project = await get_project_by_id(db, project_id, organization_id)
    if not project:
        logger.warning(f"Project not found: project_id={project_id}")
        return False, "Project not found or you don't have access to it"

    user = await get_user_by_id(db, user_id, organization_id)
    if not user:
        logger.warning(f"User not found in organization: user_id={user_id}")
        return False, "User not found in your organization"

    if await check_project_user_exists(db, project_id, user_id):
        logger.warning(f"User already in project: user_id={user_id}, project_id={project_id}")
        return False, "User already added to project"

    project_user = ProjectUser(project_id=project_id, user_id=user_id)
    db.add(project_user)
    await db.commit()

    logger.info(f"User added to project successfully: user_id={user_id}, project_id={project_id}")

    return True, "User successfully added to project"


async def remove_user_from_project_service(
    db: AsyncSession, project_id: UUID, user_id: UUID, organization_id: UUID
) -> tuple[bool, str]:
    """
    Remove user from project.

    Args:
        db: Database session
        project_id: Project UUID
        user_id: User UUID to remove
        organization_id: Organization UUID

    Returns:
        Tuple of (success: bool, message: str)
    """
    logger.info(f"Removing user_id={user_id} from project_id={project_id}")

    project = await get_project_by_id(db, project_id, organization_id)
    if not project:
        logger.warning(f"Project not found: project_id={project_id}")
        return False, "Project not found or you don't have access to it"

    statement = select(ProjectUser).where(
        and_(ProjectUser.project_id == project_id, ProjectUser.user_id == user_id)
    )
    # prefer SQLModel AsyncSession.execute which returns a ScalarResult
    result = await db.execute(statement)
    project_user = result.one_or_none()

    if not project_user:
        logger.warning(f"User not in project: user_id={user_id}, project_id={project_id}")
        return False, "User is not a member of this project"

    await db.delete(project_user)
    await db.commit()

    logger.info(
        f"User removed from project successfully: user_id={user_id}, project_id={project_id}"
    )

    return True, "User successfully removed from project"
