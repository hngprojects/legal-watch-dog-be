"""
Audit Service
Provides logging methods for all project operations.

This module implements a production-grade ProjectAuditService that:
- Groups methods into PROJECT-LEVEL and ORG/GLOBAL sections (Option A).
- Allows non-project logs (project_id optional) where applicable.
- Provides a single private _log() builder to reduce repetition.
- Uses a safe repository wrapper _safe_log() so audit failures never break upstream code.
- Uses conservative defaults when aggregating (limit=10_000) to avoid OOM.
- Uses AuditAction.value for stable, human-friendly action strings in summaries/serializations.
- All public methods include full method-level docstrings (Args + Returns).
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.api.modules.v1.projects.models.project_audit_log import (
    AuditAction,
    ProjectAuditLog,
)
from app.api.modules.v1.projects.repositories.audit_repository import (
    ProjectAuditRepository,
)
from app.api.modules.v1.projects.schemas.audit_schemas import AuditStatsResponse

logger = logging.getLogger(__name__)


class ProjectAuditService:
    """
    Service for logging and querying project-related audit events.

    This service acts as a thin business layer over ProjectAuditRepository.
    It provides:
    - Safe writes via `_safe_log`
    - A compact `_log` builder for constructing audit entries
    - Read methods that forward to repository with conservative defaults
    """

    def __init__(self, repository: ProjectAuditRepository):
        """
        Initialize the audit service.

        Args:
            repository (ProjectAuditRepository): Repository instance used to persist and
                query audit logs.
        """
        self.repository = repository

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
        Retrieve paginated audit logs for a specific project.

        Args:
            project_id (UUID): Project UUID to filter logs by.
            action (Optional[AuditAction]): Optional action filter.
            user_id (Optional[UUID]): Optional user filter.
            date_from (Optional[datetime]): Start datetime filter (inclusive).
            date_to (Optional[datetime]): End datetime filter (inclusive).
            page (int): Pagination page number (1-based).
            limit (int): Items per page.

        Returns:
            Tuple[List[ProjectAuditLog], int]: (logs, total_count)
        """
        return await self.repository.get_project_audit_logs(
            project_id=project_id,
            action=action,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )

    async def get_jurisdiction_audit_logs(
        self,
        jurisdiction_id: UUID,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[ProjectAuditLog], int]:
        """
        Retrieve paginated audit logs for a jurisdiction.

        Args:
            jurisdiction_id (UUID): Jurisdiction UUID to filter logs by.
            page (int): Pagination page number.
            limit (int): Items per page.

        Returns:
            Tuple[List[ProjectAuditLog], int]: (logs, total_count)
        """
        return await self.repository.get_jurisdiction_audit_logs(
            jurisdiction_id=jurisdiction_id, page=page, limit=limit
        )

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
        Retrieve paginated audit logs for an organization.

        Args:
            org_id (UUID): Organization UUID to filter logs by.
            action (Optional[AuditAction]): Optional action filter.
            date_from (Optional[datetime]): Start datetime filter.
            date_to (Optional[datetime]): End datetime filter.
            page (int): Pagination page number.
            limit (int): Items per page.

        Returns:
            Tuple[List[ProjectAuditLog], int]: (logs, total_count)
        """
        return await self.repository.get_organization_audit_logs(
            org_id=org_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )

    async def get_audit_log_by_id(self, log_id: int, org_id: UUID) -> Optional[ProjectAuditLog]:
        """
        Retrieve a single audit log by integer ID and organization scope.

        Args:
            log_id (int): Integer ID of the audit log record.
            org_id (UUID): Organization UUID to scope lookup.

        Returns:
            Optional[ProjectAuditLog]: The found log or None.
        """
        return await self.repository.get_audit_log_by_id(log_id=log_id, org_id=org_id)

    async def _safe_log(self, log: ProjectAuditLog) -> Optional[ProjectAuditLog]:
        """
        Persist an audit log through repository safely.

        Any exception is caught and logged; None is returned on failure so that
        audit failures do not break business flows.

        Args:
            log (ProjectAuditLog): The audit log model instance to persist.

        Returns:
            Optional[ProjectAuditLog]: Persisted log or None if the write failed.
        """
        try:
            return await self.repository.log_action(log)
        except Exception as exc:
            # Always log the failure but do not propagate
            action_str = getattr(log.action, "value", str(log.action))
            logger.error(
                "Audit logging failed for action %s: %s", action_str, str(exc), exc_info=True
            )
            return None

    def _log(
        self,
        *,
        action: AuditAction,
        org_id: UUID,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        jurisdiction_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProjectAuditLog:
        """
        Build a ProjectAuditLog instance with normalized fields.

        This is a small builder to keep public methods concise and consistent.

        Args:
            action (AuditAction): Enum member for the action.
            org_id (UUID): Organization UUID.
            user_id (UUID): User UUID performing the action.
            project_id (Optional[UUID]): Optional project UUID.
            jurisdiction_id (Optional[UUID]): Optional jurisdiction UUID.
            source_id (Optional[UUID]): Optional source UUID.
            details (Optional[Dict[str, Any]]): Structured details (will be coerced to dict).
            ip_address (Optional[str]): IP address string.
            user_agent (Optional[str]): User agent string.

        Returns:
            ProjectAuditLog: Unpersisted ProjectAuditLog instance ready for _safe_log.
        """
        normalized_details = self._ensure_dict(details)
        return ProjectAuditLog(
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            source_id=source_id,
            org_id=org_id,
            user_id=user_id,
            action=action,
            details=normalized_details,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
        )

    async def get_audit_statistics(
        self,
        org_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        *,
        aggregation_limit: int = 10_000,
    ) -> AuditStatsResponse:
        """
        Returns aggregated audit statistics for an organization.

        Uses a conservative default limit (10_000) to avoid OOM; callers may
        override via `aggregation_limit` if they understand the risk.

        Args:
            org_id (UUID): Organization UUID to aggregate logs for.
            date_from (Optional[datetime]): Start datetime filter.
            date_to (Optional[datetime]): End datetime filter.
            aggregation_limit (int): Max number of logs to fetch for aggregation.

        Returns:
            AuditStatsResponse: Aggregated statistics including total_logs, by_action,
                by_user, and date_range.
        """
        # Fetch logs conservatively
        logs, _ = await self.repository.get_organization_audit_logs(
            org_id=org_id,
            date_from=date_from,
            date_to=date_to,
            page=1,
            limit=aggregation_limit,
        )

        total_logs = len(logs)

        by_action: Dict[str, int] = {}
        by_user: Dict[str, int] = {}

        for log in logs:
            action_key = getattr(log.action, "value", str(log.action))
            by_action[action_key] = by_action.get(action_key, 0) + 1
            user_key = str(log.user_id) if log.user_id is not None else "unknown"
            by_user[user_key] = by_user.get(user_key, 0) + 1

        date_range: Dict[str, datetime] = {}
        if date_from:
            date_range["start"] = date_from
        if date_to:
            date_range["end"] = date_to

        return AuditStatsResponse(
            total_logs=total_logs,
            by_action=by_action,
            by_user=by_user,
            date_range=date_range,
        )

    @staticmethod
    def _ensure_dict(value: Any) -> Dict[str, Any]:
        """
        Ensure a value is a dictionary (return {} otherwise).

        Args:
            value (Any): Candidate details/changes value.

        Returns:
            Dict[str, Any]: The value if dict, otherwise an empty dict.
        """
        return value if isinstance(value, dict) else {}

    async def log_project_created(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a project was created.

        Args:
            project_id (UUID): Created project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who created the project.
            details (Dict[str, Any]): Extra details about the project (coerced to dict).
            ip_address (Optional[str]): Creator's IP address.
            user_agent (Optional[str]): Creator's user agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        log = self._log(
            action=AuditAction.PROJECT_CREATED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_project_updated(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a project was updated.

        Args:
            project_id (UUID): Project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who updated the project.
            changes (Dict[str, Any]): A dictionary describing changes; 
                This will be stored under the 'changes' key.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        details = {"changes": self._ensure_dict(changes)}
        log = self._log(
            action=AuditAction.PROJECT_UPDATED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_project_deleted(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a project was deleted (soft or hard based on calling code).

        Args:
            project_id (UUID): Project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who deleted the project.
            reason (Optional[str]): Short reason string (optional).
            details (Optional[Dict[str, Any]]): Additional details.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        payload = self._ensure_dict(details)
        if reason:
            payload.setdefault("reason", reason)

        log = self._log(
            action=AuditAction.PROJECT_DELETED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            details=payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_jurisdiction_created(
        self,
        jurisdiction_id: UUID,
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a jurisdiction was created.

        Note: project_id is optional to allow non-project-bound jurisdictions.

        Args:
            jurisdiction_id (UUID): Jurisdiction id.
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who created the jurisdiction.
            details (Dict[str, Any]): Additional structured details.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        log = self._log(
            action=AuditAction.JURISDICTION_CREATED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_jurisdiction_updated(
        self,
        jurisdiction_id: UUID,
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a jurisdiction was updated.

        Args:
            jurisdiction_id (UUID): Jurisdiction id.
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who updated the jurisdiction.
            changes (Dict[str, Any]): Dict describing changes stored under 'changes'.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        details = {"changes": self._ensure_dict(changes)}
        log = self._log(
            action=AuditAction.JURISDICTION_UPDATED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_jurisdiction_parent_changed(
        self,
        jurisdiction_id: UUID,
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        old_parent_id: Optional[UUID],
        new_parent_id: Optional[UUID],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a jurisdiction's parent was changed.

        Args:
            jurisdiction_id (UUID): Jurisdiction id.
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who changed the parent.
            old_parent_id (Optional[UUID]): Previous parent id.
            new_parent_id (Optional[UUID]): New parent id.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        details = {"old_parent_id": old_parent_id, "new_parent_id": new_parent_id}
        log = self._log(
            action=AuditAction.JURISDICTION_PARENT_CHANGED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_master_prompt_updated(
        self,
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        old_prompt: Optional[str],
        new_prompt: Optional[str],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a project's master prompt was updated.

        Args:
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who updated the prompt.
            old_prompt (Optional[str]): Previous prompt.
            new_prompt (Optional[str]): New prompt.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        details = {"old_prompt": old_prompt, "new_prompt": new_prompt}
        log = self._log(
            action=AuditAction.MASTER_PROMPT_UPDATED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_override_prompt_updated(
        self,
        jurisdiction_id: UUID,
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        old_prompt: Optional[str],
        new_prompt: Optional[str],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a jurisdiction override prompt was updated.

        Args:
            jurisdiction_id (UUID): Jurisdiction id.
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who updated the override.
            old_prompt (Optional[str]): Previous override prompt.
            new_prompt (Optional[str]): New override prompt.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        details = {"old_prompt": old_prompt, "new_prompt": new_prompt}
        log = self._log(
            action=AuditAction.OVERRIDE_PROMPT_UPDATED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_source_assigned(
        self,
        source_id: UUID,
        jurisdiction_id: Optional[UUID],
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a source was assigned to a jurisdiction/project.

        Args:
            source_id (UUID): Source id.
            jurisdiction_id (Optional[UUID]): Optional jurisdiction id.
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who assigned the source.
            details (Dict[str, Any]): Additional structured details.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        log = self._log(
            action=AuditAction.SOURCE_ASSIGNED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            source_id=source_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)

    async def log_source_unassigned(
        self,
        source_id: UUID,
        jurisdiction_id: Optional[UUID],
        project_id: Optional[UUID],
        org_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ProjectAuditLog]:
        """
        Log that a source was unassigned from a jurisdiction/project.

        Args:
            source_id (UUID): Source id.
            jurisdiction_id (Optional[UUID]): Optional jurisdiction.
            project_id (Optional[UUID]): Optional project id.
            org_id (UUID): Organization id.
            user_id (UUID): User who unassigned the source.
            reason (Optional[str]): Short reason string.
            ip_address (Optional[str]): IP address.
            user_agent (Optional[str]): User agent.

        Returns:
            Optional[ProjectAuditLog]: Persisted audit log or None on failure.
        """
        details = {"reason": reason} if reason else {}
        log = self._log(
            action=AuditAction.SOURCE_UNASSIGNED,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            source_id=source_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self._safe_log(log)
