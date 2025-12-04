"""
Repository for Project Audit Log database operations.

This module provides a repository class, `ProjectAuditRepository`, which encapsulates
all database interactions related to project audit logs. It expects an injected
`AsyncSession` (from `get_db`) and **does not** perform commit/rollback/close
operations itself — transaction lifecycle is handled by the calling context
(see `app.api.db.database.get_db`).
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.projects.models.project_audit_log import (
    AuditAction,
    ProjectAuditLog,
)

logger = logging.getLogger(__name__)


class ProjectAuditRepository:
    """
    Repository for project, jurisdiction, and organization audit log operations.

    Responsibilities:
      * Run read queries for audit logs with filtering and pagination.
      * Insert audit log entries into the database (only add + flush; no commits).
      * Leave transaction management (commit/rollback/close) to the session provider
        (e.g. the FastAPI dependency that yields an AsyncSession).

    Attributes:
        db (AsyncSession): Async SQLModel/SQLAlchemy session provided by the caller.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the repository.

        Args:
            db (AsyncSession): Active async database session (injected via Depends(get_db)).
        """
        self.db = db

    async def log_action(self, audit_log: ProjectAuditLog) -> ProjectAuditLog:
        """
        Insert a new audit log entry into the database.

        Notes:
            - This method only calls `add()` and `flush()` to persist the object to
              the current transaction. It does NOT commit or rollback; the caller's
              session manager is responsible for committing the transaction.
            - If you require the inserted object to have database-generated fields
              available immediately, call `await self.db.flush()` before returning.
              This function already calls `flush()`.

        Args:
            audit_log (ProjectAuditLog): The audit log model instance to persist.

        Returns:
            ProjectAuditLog: The same `audit_log` instance (with DB-populated fields
            available after flush).

        Raises:
            RuntimeError: If writing to the database fails.
        """
        try:
            self.db.add(audit_log)
            await self.db.flush()
            return audit_log
        except SQLAlchemyError as e:
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
        Retrieve audit logs for a specific project with optional filters and pagination.

        Args:
            project_id (UUID): The project ID to filter logs by.
            action (Optional[AuditAction]): Filter by action type (optional).
            user_id (Optional[UUID]): Filter by user ID (optional).
            date_from (Optional[datetime]): Include logs created at or after this timestamp.
            date_to (Optional[datetime]): Include logs created at or before this timestamp.
            page (int): Page number for pagination (1-indexed).
            limit (int): Number of items per page.

        Returns:
            Tuple[List[ProjectAuditLog], int]: A tuple of (logs list, total_count).

        Raises:
            RuntimeError: If a database error occurs while fetching logs.
        """
        try:
            stmt = select(ProjectAuditLog).where(ProjectAuditLog.project_id == project_id)

            if action is not None:
                stmt = stmt.where(ProjectAuditLog.action == action)
            if user_id is not None:
                stmt = stmt.where(ProjectAuditLog.user_id == user_id)
            if date_from is not None:
                stmt = stmt.where(ProjectAuditLog.created_at >= date_from)
            if date_to is not None:
                stmt = stmt.where(ProjectAuditLog.created_at <= date_to)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await self.db.execute(count_stmt)).scalar() or 0

            offset = (page - 1) * limit
            stmt = stmt.order_by(ProjectAuditLog.created_at.desc()).offset(offset).limit(limit)

            result = await self.db.execute(stmt)
            logs = result.scalars().all()

            return logs, total

        except Exception as e:
            logger.error("Failed fetching project audit logs: %s", e, exc_info=True)
            raise RuntimeError("Project audit logs read failed") from e

    async def get_jurisdiction_audit_logs(
        self, jurisdiction_id: UUID, page: int = 1, limit: int = 50
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Retrieve audit logs for a specific jurisdiction with pagination.

        Args:
            jurisdiction_id (UUID): The jurisdiction ID to filter logs by.
            page (int): Page number for pagination (1-indexed).
            limit (int): Number of items per page.

        Returns:
            Tuple[List[ProjectAuditLog], int]: A tuple of (logs list, total_count).

        Raises:
            RuntimeError: If a database error occurs while fetching logs.
        """
        try:
            stmt = select(ProjectAuditLog).where(ProjectAuditLog.jurisdiction_id == jurisdiction_id)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await self.db.execute(count_stmt)).scalar() or 0

            offset = (page - 1) * limit
            stmt = stmt.order_by(ProjectAuditLog.created_at.desc()).offset(offset).limit(limit)

            result = await self.db.execute(stmt)
            logs = result.scalars().all()

            return logs, total

        except Exception as e:
            logger.error("Failed fetching jurisdiction audit logs: %s", e, exc_info=True)
            raise RuntimeError("Jurisdiction audit logs read failed") from e

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
        Retrieve audit logs for an organization with optional filters and pagination.

        Args:
            org_id (UUID): The organization ID to filter logs by.
            action (Optional[AuditAction]): Filter by action type (optional).
            date_from (Optional[datetime]): Include logs created at or after this timestamp.
            date_to (Optional[datetime]): Include logs created at or before this timestamp.
            page (int): Page number for pagination (1-indexed).
            limit (int): Number of items per page.

        Returns:
            Tuple[List[ProjectAuditLog], int]: A tuple of (logs list, total_count).

        Raises:
            RuntimeError: If a database error occurs while fetching logs.
        """
        try:
            stmt = select(ProjectAuditLog).where(ProjectAuditLog.org_id == org_id)

            if action is not None:
                stmt = stmt.where(ProjectAuditLog.action == action)
            if date_from is not None:
                stmt = stmt.where(ProjectAuditLog.created_at >= date_from)
            if date_to is not None:
                stmt = stmt.where(ProjectAuditLog.created_at <= date_to)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await self.db.execute(count_stmt)).scalar() or 0

            offset = (page - 1) * limit
            stmt = stmt.order_by(ProjectAuditLog.created_at.desc()).offset(offset).limit(limit)

            result = await self.db.execute(stmt)
            logs = result.scalars().all()

            return logs, total

        except Exception as e:
            logger.exception("Failed fetching organization audit logs: %s", e, exc_info=True)
            raise RuntimeError("Organization audit logs read failed") from e

    async def get_audit_log_by_id(self, log_id: int, org_id: UUID) -> Optional[ProjectAuditLog]:
        """
        Retrieve a single audit log entry by its integer log_id and organization.

        Args:
            log_id (int): The integer ID of the audit log (primary key).
            org_id (UUID): The organization ID to scope the lookup.

        Returns:
            Optional[ProjectAuditLog]: The matching audit log or None if not found.

        Raises:
            RuntimeError: If a database error occurs while fetching the log.
        """
        try:
            stmt = select(ProjectAuditLog).where(
                ProjectAuditLog.log_id == log_id,
                ProjectAuditLog.org_id == org_id,
            )
            result = await self.db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.exception("Failed to fetch audit log by ID: %s", e, exc_info=True)
            raise RuntimeError("Audit log lookup failed") from e
