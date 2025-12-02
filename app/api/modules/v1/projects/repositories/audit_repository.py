"""
Repository for Project Audit Log database operations
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.projects.models.project_audit_log import (
    AuditAction,
    ProjectAuditLog,
)

logger = logging.getLogger(__name__)


class ProjectAuditRepository:
    """Repository for project audit log operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_action(self, audit_log: ProjectAuditLog) -> ProjectAuditLog:
        """
        Create an audit log entry.
        Wrapped with robust error handling so audit failures never corrupt the session.
        """
        try:
            self.session.add(audit_log)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(audit_log)
            return audit_log
        except SQLAlchemyError as e:
            try:
                await self.session.rollback()
            except Exception:
                pass
            logger.error("Failed to write audit log: %s", e, exc_info=True)
            raise RuntimeError("Audit repository write failed") from e

    async def get_project_audit_logs(
        self,
        project_id: UUID,
        action: Optional[AuditAction] = None,
        user_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Get audit logs for a project with filters.
        """
        try:
            # Base query
            stmt = select(ProjectAuditLog).where(
                ProjectAuditLog.project_id == project_id
            )

            if action:
                stmt = stmt.where(ProjectAuditLog.action == action)
            if user_id:
                stmt = stmt.where(ProjectAuditLog.user_id == user_id)
            if date_from:
                stmt = stmt.where(ProjectAuditLog.created_at >= date_from)
            if date_to:
                stmt = stmt.where(ProjectAuditLog.created_at <= date_to)

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            result = await self.session.execute(count_stmt)
            total_count = result.scalar() or 0

            # Pagination
            offset = (page - 1) * limit
            stmt = (
                stmt.order_by(ProjectAuditLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            )

            logs_result = await self.session.execute(stmt)
            logs = logs_result.scalars().all()

            return logs, total_count

        except Exception as e:
            logger.error(
                "Failed to fetch project audit logs: %s", str(e), exc_info=True
            )
            raise RuntimeError("Audit repository read failed") from e

    async def get_jurisdiction_audit_logs(
        self, jurisdiction_id: UUID, page: int = 1, limit: int = 50
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Get audit logs for a specific jurisdiction.

        """
        try:
            stmt = select(ProjectAuditLog).where(
                ProjectAuditLog.jurisdiction_id == jurisdiction_id
            )

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            result = await self.session.execute(count_stmt)
            total_count = result.scalar() or 0

            # Pagination
            offset = (page - 1) * limit
            stmt = (
                stmt.order_by(ProjectAuditLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            )

            logs_result = await self.session.execute(stmt)
            logs = logs_result.scalars().all()

            return logs, total_count

        except Exception as e:
            logger.error(
                "Failed to fetch jurisdiction audit logs: %s", str(e), exc_info=True
            )
            raise RuntimeError("Audit repository read failed") from e

    async def get_organization_audit_logs(
        self,
        org_id: UUID,
        action: Optional[AuditAction] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        limit: int = 100,
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Get all audit logs for an organization (compliance monitoring).

        """
        try:
            stmt = select(ProjectAuditLog).where(ProjectAuditLog.org_id == org_id)

            if action:
                stmt = stmt.where(ProjectAuditLog.action == action)
            if date_from:
                stmt = stmt.where(ProjectAuditLog.created_at >= date_from)
            if date_to:
                stmt = stmt.where(ProjectAuditLog.created_at <= date_to)

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            result = await self.session.execute(count_stmt)
            total_count = result.scalar() or 0

            # Pagination
            offset = (page - 1) * limit
            stmt = (
                stmt.order_by(ProjectAuditLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            )

            logs_result = await self.session.execute(stmt)
            logs = logs_result.scalars().all()

            return logs, total_count

        except Exception:
            logger.exception("Failed to fetch organization audit logs")
            raise

    async def get_audit_log_by_id(self, log_id: int, org_id: UUID):
        """
        Fetch a single audit log by its integer ID constrained to an organization.
        Returns the ProjectAuditLog or None if not found.
        """
        try:
            stmt = select(ProjectAuditLog).where(
                ProjectAuditLog.log_id == log_id, ProjectAuditLog.org_id == org_id
            )
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except Exception:
            logger.exception("Failed to fetch audit log by id")
            raise
