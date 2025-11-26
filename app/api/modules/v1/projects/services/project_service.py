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


class ProjectService:
    """
    Service class for project-related business logic operations.

    This class encapsulates all project operations including creation,
    retrieval, updates, deletion, and user management.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the ProjectService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    async def create_project(
        self,
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
            f"Creating '{data.title}' for organization_id={organization_id}, user_id={user_id}"
        )

        project = Project(
            title=data.title,
            description=data.description,
            org_id=organization_id,
        )

        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        logger.info(f"Created project with id={project.id}")

        return project

    async def list_projects(
        self,
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
            f"Projects for organization_id={organization_id}, q={q}, page={page}, limit={limit}"
        )

        statement = select(Project).where(
            and_(Project.org_id == organization_id, Project.is_deleted.is_(False))
        )
        logger.info(f"Base SQL: {str(statement)}")
        if q:
            statement = statement.where(Project.title.ilike(f"%{q}%"))
            logger.info(f"Applied search filter: q={q}")

        count_statement = select(func.count()).select_from(statement.subquery())
        total_result = await self.db.execute(count_statement)
        total = total_result.scalar_one()

        logger.info(f"Found {total} projects matching criteria")

        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit).order_by(Project.created_at.desc())
        result = await self.db.execute(statement)
        projects = result.scalars().all()

        pagination = calculate_pagination(total, page, limit)

        return {"data": projects, **pagination}

    async def get_project_by_id(self, project_id: UUID, organization_id: UUID) -> Optional[Project]:
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

        project = await get_project_by_id(self.db, project_id, organization_id)

        if project:
            logger.info(f"Project found: {project.title}")
        else:
            logger.warning(f"Project not found or no access: project_id={project_id}")

        return project

    async def update_project(
        self,
        project_id: UUID,
        organization_id: UUID,
        data: ProjectUpdate,
    ) -> tuple[Optional[Project]]:
        """
        Update project with provided data.

        Args:
            project_id: Project UUID
            organization_id: Organization UUID
            data: Update data
        """
        logger.info(f"Updating project_id={project_id}")

        project = await get_project_by_id(self.db, project_id, organization_id)

        if not project:
            logger.warning(f"Project not found for update: project_id={project_id}")
            return None, "Project not found"

        update_data = data.model_dump(exclude_unset=True)
        changes_made = False

        for field, value in update_data.items():
            setattr(project, field, value)
            changes_made = True
            logger.info(f"Updated field '{field}' for project_id={project_id}")

        if changes_made:
            project.updated_at = datetime.now(timezone.utc)
            self.db.add(project)
            await self.db.commit()
            await self.db.refresh(project)

        logger.info(f"Project updated successfully: project_id={project_id}")

        return project

    async def delete_project(self, project_id: UUID, organization_id: UUID) -> bool:
        """
        Permanently delete project from database (irreversible).

        Args:
            db: Database session
            project_id: Project UUID
            organization_id: Organization UUID

        Returns:
            True if deleted, False if not found
        """
        logger.warning(f"hard deleting project_id={project_id}")

        project = await get_project_by_id_including_deleted(self.db, project_id, organization_id)

        if not project:
            logger.warning(f"Project not found for hard delete: project_id={project_id}")
            return False

        await self.db.delete(project)
        await self.db.commit()

        logger.warning(f"Project deleted permanently: project_id={project_id}")

        return True

    async def soft_delete_project(
        self, project_id: UUID, organization_id: UUID
    ) -> Optional[Project]:
        """
        Soft delete project by marking it as deleted.

        Args:
            project_id: Project UUID
            organization_id: Organization UUID

        Returns:
            Updated Project object if found, None otherwise
        """
        logger.info(f"Soft deleting project_id={project_id}")

        project = await get_project_by_id(self.db, project_id, organization_id)

        if not project:
            logger.warning(f"Project not found for soft delete: project_id={project_id}")
            return None

        project.is_deleted = True
        project.deleted_at = datetime.now(timezone.utc)
        project.updated_at = datetime.now(timezone.utc)

        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        logger.info(f"Project soft deleted successfully: project_id={project_id}")

        return project

    async def get_users(self, project_id: UUID, organization_id: UUID) -> Optional[List[UUID]]:
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

        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            return None

        statement = select(ProjectUser.user_id).where(ProjectUser.project_id == project_id)
        result = await self.db.execute(statement)
        user_ids = result.all()

        logger.info(f"Found {len(user_ids)} users in project_id={project_id}")

        return list(user_ids)

    async def add_user(
        self, project_id: UUID, user_id: UUID, organization_id: UUID
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

        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            return False, "Project not found or you don't have access to it"

        user = await get_user_by_id(self.db, user_id, organization_id)
        if not user:
            logger.warning(f"User not found in organization: user_id={user_id}")
            return False, "User not found in your organization"

        if await check_project_user_exists(self.db, project_id, user_id):
            logger.warning(f"User already in project: user_id={user_id}, project_id={project_id}")
            return False, "User already added to project"

        project_user = ProjectUser(project_id=project_id, user_id=user_id)
        self.db.add(project_user)
        await self.db.commit()

        logger.info(
            f"User added to project successfully: user_id={user_id}, project_id={project_id}"
        )

        return True, "User successfully added to project"

    async def remove_user(
        self, project_id: UUID, user_id: UUID, organization_id: UUID
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

        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            return False, "Project not found or you don't have access to it"

        statement = select(ProjectUser).where(
            and_(ProjectUser.project_id == project_id, ProjectUser.user_id == user_id)
        )
        # prefer SQLModel AsyncSession.execute which returns a ScalarResult
        result = await self.db.execute(statement)
        project_user = result.one_or_none()

        if not project_user:
            logger.warning(f"User not in project: user_id={user_id}, project_id={project_id}")
            return False, "User is not a member of this project"

        await self.db.delete(project_user)
        await self.db.commit()

        logger.info(
            f"User removed from project successfully: user_id={user_id}, project_id={project_id}"
        )

        return True, "User successfully removed from project"
