# app/api/modules/v1/projects/service/audit_service.py
"""
Audit Service
Provides logging methods for all project operations
"""

import logging
from typing import Any, Dict, Optional

from app.api.modules.v1.projects.models.project_audit_log import AuditAction, ProjectAuditLog
from app.api.modules.v1.projects.repositories.audit_repository import ProjectAuditRepository

logger = logging.getLogger(__name__)


class ProjectAuditService:
    """
    Service for logging project-related audit events.
    Includes robust error handling so failures never break the app.
    """

    def __init__(self, repository: ProjectAuditRepository):
        self.repository = repository

    def _safe_log(self, log: ProjectAuditLog) -> Optional[ProjectAuditLog]:
        """
        Wraps all repository calls in safe try/except.
        Audit failures should never break upstream services.
        """
        try:
            return self.repository.log_action(log)

        except Exception as e:
        
            logger.error(
                "Audit logging failed for action %s: %s",
                log.action.value,
                str(e),
                exc_info=True
            )
            
            return None

    # ===== UTILITIES =====

    @staticmethod
    def _ensure_dict(value: Any) -> Dict[str, Any]:
        """Guarantees details/changes are dictionaries to prevent crashes."""
        return value if isinstance(value, dict) else {}

    # ===== PROJECT ACTIONS =====

    def log_project_created(
        self,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    def log_project_updated(
        self,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    def log_project_deleted(
        self,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    # ===== JURISDICTION ACTIONS =====

    def log_jurisdiction_created(
        self,
        jurisdiction_id: int,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    def log_jurisdiction_updated(
        self,
        jurisdiction_id: int,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    def log_jurisdiction_parent_changed(
        self,
        jurisdiction_id: int,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    # ===== PROMPT ACTIONS =====

    def log_master_prompt_updated(
        self,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    def log_override_prompt_updated(
        self,
        jurisdiction_id: int,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    # ===== SOURCE ACTIONS =====

    def log_source_assigned(
        self,
        source_id: int,
        jurisdiction_id: int,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)

    def log_source_unassigned(
        self,
        source_id: int,
        jurisdiction_id: int,
        project_id: int,
        org_id: int,
        user_id: int,
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
        return self._safe_log(log)
