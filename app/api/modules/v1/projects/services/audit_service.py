# app/api/modules/v1/projects/service/audit_service.py
"""
Audit Service
Provides logging methods for all project operations
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from app.api.modules.v1.projects.models.project_audit_log import AuditAction, ProjectAuditLog
from app.api.modules.v1.projects.repositories.audit_repository import ProjectAuditRepository
from app.api.modules.v1.projects.schemas.audit_schemas import AuditStatsResponse

logger = logging.getLogger(__name__)


class ProjectAuditService:
    """
    Service for logging project-related audit events.
    Includes robust error handling so failures never break the app.
    """

    def __init__(self, repository: ProjectAuditRepository):
        self.repository = repository

    async def get_project_audit_logs(self, **filters):
        return await self.repository.get_project_audit_logs(**filters)

    async def get_jurisdiction_audit_logs(self, **filters):
        return await self.repository.get_jurisdiction_audit_logs(**filters)

    async def get_organization_audit_logs(self, **filters):
        return await self.repository.get_organization_audit_logs(**filters)
    
    async def _safe_log(self, log: ProjectAuditLog) -> Optional[ProjectAuditLog]:

        """
        Wraps all repository calls in safe try/except.
        Audit failures should never break upstream services.
        """

        try:
            return await self.repository.log_action(log)
        except Exception as e:
            logger.error("Audit logging failed for action %s: %s",
                        log.action.value, str(e), exc_info=True)
            return None

    
    async def get_audit_statistics(
        self,
        org_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> AuditStatsResponse:
        """
        Returns aggregated audit statistics for an organization.

        Notes:
        - Fetches logs through the repository (service layer requirement)
        - Builds summaries for total count, actions, and users
        - Zero breaking changes; mirrors router's expected output
        """
        logs, _ = await self.repository.get_organization_audit_logs(
            org_id=org_id,
            date_from=date_from,
            date_to=date_to,
            page=1,
            limit=100000   # Retrieve all logs for aggregation
        )

        total_logs = len(logs)

        # Aggregate stats
        by_action: Dict[str, int] = {}
        by_user: Dict[str, int] = {}

        for log in logs:
            by_action[str(log.action)] = by_action.get(str(log.action), 0) + 1
            by_user[str(log.user_id)] = by_user.get(str(log.user_id), 0) + 1

        date_range: Dict[str, datetime] = {}
        if date_from:
            date_range["start"] = date_from
        if date_to:
            date_range["end"] = date_to

        return AuditStatsResponse(
            total_logs=total_logs,
            by_action=by_action,
            by_user=by_user,
            date_range=date_range
        )

    # ===== UTILITIES =====

    @staticmethod
    def _ensure_dict(value: Any) -> Dict[str, Any]:
        """Guarantees details/changes are dictionaries to prevent crashes."""
        return value if isinstance(value, dict) else {}

    # ===== PROJECT ACTIONS =====

    async def log_project_created(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        details = self._ensure_dict(details)
        log = ProjectAuditLog(
            project_id=project_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.PROJECT_CREATED,
            details=details,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    async def log_project_updated(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        changes = self._ensure_dict(changes)
        log = ProjectAuditLog(
            project_id=project_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.PROJECT_UPDATED,
            details={"changes": changes},
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    async def log_project_deleted(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        log = ProjectAuditLog(
            project_id=project_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.PROJECT_DELETED,
            details={"reason": reason} if reason else {},
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    # ===== JURISDICTION ACTIONS =====

    async def log_jurisdiction_created(
        self,
        jurisdiction_id: int,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        details = self._ensure_dict(details)
        log = ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.JURISDICTION_CREATED,
            details=details,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    async def log_jurisdiction_updated(
        self,
        jurisdiction_id: int,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        changes = self._ensure_dict(changes)
        log = ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.JURISDICTION_UPDATED,
            details={"changes": changes},
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    async def log_jurisdiction_parent_changed(
        self,
        jurisdiction_id: int,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        old_parent_id: Optional[int],
        new_parent_id: Optional[int],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        log = ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.JURISDICTION_PARENT_CHANGED,
            details={
                "old_parent_id": old_parent_id,
                "new_parent_id": new_parent_id
            },
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    # ===== PROMPT ACTIONS =====

    async def log_master_prompt_updated(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        old_prompt: str,
        new_prompt: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        log = ProjectAuditLog(
            project_id=project_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.MASTER_PROMPT_UPDATED,
            details={
                "old_prompt": old_prompt,
                "new_prompt": new_prompt
            },
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    async def log_override_prompt_updated(
        self,
        jurisdiction_id: int,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        old_prompt: Optional[str],
        new_prompt: Optional[str],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        log = ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.OVERRIDE_PROMPT_UPDATED,
            details={
                "old_prompt": old_prompt,
                "new_prompt": new_prompt
            },
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    # ===== SOURCE ACTIONS =====

    async def log_source_assigned(
        self,
        source_id: int,
        jurisdiction_id: int,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        details = self._ensure_dict(details)
        log = ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            source_id=source_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.SOURCE_ASSIGNED,
            details=details,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)

    async def log_source_unassigned(
        self,
        source_id: int,
        jurisdiction_id: int,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ProjectAuditLog]:
        log = ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            source_id=source_id,
            org_id=org_id,
            user_id=user_id,
            action=AuditAction.SOURCE_UNASSIGNED,
            details={"reason": reason} if reason else {},
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown"
        )
        return await self._safe_log(log)
