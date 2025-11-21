# app/api/modules/v1/projects/repositories/audit_repository.py
"""
Repository for Project Audit Log database operations
"""
import logging
from sqlmodel import Session, select, func
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Tuple
from datetime import datetime

from app.api.modules.v1.projects.models.project_audit_log import ProjectAuditLog, AuditAction

logger = logging.getLogger(__name__)


class ProjectAuditRepository:
    """Repository for project audit log operations"""

    def __init__(self, session: Session):
        self.session = session

    def log_action(self, audit_log: ProjectAuditLog) -> ProjectAuditLog:
        """
        Create an audit log entry.
        Wrapped with robust error handling so audit failures never corrupt the session.
        """
        try:
            self.session.add(audit_log)

            # Flush first to detect constraint/DB errors early
            self.session.flush()

            self.session.commit()
            self.session.refresh(audit_log)
            return audit_log

        except SQLAlchemyError as e:
            # rollback protects session from becoming unusable
            try:
                self.session.rollback()
            except Exception:
                pass

            logger.error("Failed to write audit log: %s", e, exc_info=True)
            # Raise a safe error for the service layer to catch
            raise RuntimeError("Audit repository write failed") from e

    def get_project_audit_logs(
        self,
        project_id: int,
        action: Optional[AuditAction] = None,
        user_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Get audit logs for a project with filters.
        """
        try:
            statement = select(ProjectAuditLog).where(
                ProjectAuditLog.project_id == project_id
            )

            if action:
                statement = statement.where(ProjectAuditLog.action == action)

            if user_id:
                statement = statement.where(ProjectAuditLog.user_id == user_id)

            if date_from:
                statement = statement.where(ProjectAuditLog.created_at >= date_from)

            if date_to:
                statement = statement.where(ProjectAuditLog.created_at <= date_to)

            # Count total
            count_statement = select(func.count()).select_from(statement.subquery())
            total_count = self.session.exec(count_statement).one()

            # Pagination
            offset = (page - 1) * limit
            statement = statement.order_by(
                ProjectAuditLog.created_at.desc()
            ).offset(offset).limit(limit)

            logs = self.session.exec(statement).all()

            return logs, total_count

        except SQLAlchemyError as e:
            logger.error("Failed to fetch project audit logs: %s", e, exc_info=True)
            raise RuntimeError("Audit repository read failed") from e

    def get_jurisdiction_audit_logs(
        self,
        jurisdiction_id: int,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Get audit logs for a jurisdiction.
        """
        try:
            statement = select(ProjectAuditLog).where(
                ProjectAuditLog.jurisdiction_id == jurisdiction_id
            )

            count_statement = select(func.count()).select_from(statement.subquery())
            total = self.session.exec(count_statement).one()

            offset = (page - 1) * limit
            statement = statement.order_by(
                ProjectAuditLog.created_at.desc()
            ).offset(offset).limit(limit)

            logs = self.session.exec(statement).all()
            return logs, total

        except SQLAlchemyError as e:
            logger.error("Failed to fetch jurisdiction audit logs: %s", e, exc_info=True)
            raise RuntimeError("Audit repository read failed") from e

    def get_organization_audit_logs(
        self,
        org_id: int,
        action: Optional[AuditAction] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        limit: int = 100
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Get all audit logs for an organization (compliance monitoring).
        """
        try:
            statement = select(ProjectAuditLog).where(
                ProjectAuditLog.org_id == org_id
            )

            if action:
                statement = statement.where(ProjectAuditLog.action == action)

            if date_from:
                statement = statement.where(ProjectAuditLog.created_at >= date_from)

            if date_to:
                statement = statement.where(ProjectAuditLog.created_at <= date_to)

            # Count
            count_statement = select(func.count()).select_from(statement.subquery())
            total = self.session.exec(count_statement).one()

            # Pagination
            offset = (page - 1) * limit
            statement = statement.order_by(
                ProjectAuditLog.created_at.desc()
            ).offset(offset).limit(limit)

            logs = self.session.exec(statement).all()
            return logs, total

        except SQLAlchemyError as e:
            logger.error("Failed to fetch organization audit logs: %s", e, exc_info=True)
            raise RuntimeError("Audit repository read failed") from e
