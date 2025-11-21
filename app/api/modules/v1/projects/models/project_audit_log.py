# app/api/modules/v1/projects/models/project_audit_log.py
"""
Project Audit Log Model
Tracks all project/jurisdiction/prompt/source operations
"""

from sqlmodel import Field, SQLModel, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AuditAction(str, Enum):
    """Enum for audit action types"""
    # Project actions
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_DELETED = "project_deleted"
    
    # Jurisdiction actions
    JURISDICTION_CREATED = "jurisdiction_created"
    JURISDICTION_UPDATED = "jurisdiction_updated"
    JURISDICTION_DELETED = "jurisdiction_deleted"
    JURISDICTION_PARENT_CHANGED = "jurisdiction_parent_changed"
    
    # Prompt actions
    MASTER_PROMPT_UPDATED = "master_prompt_updated"
    OVERRIDE_PROMPT_UPDATED = "override_prompt_updated"
    
    # Source actions
    SOURCE_ASSIGNED = "source_assigned"
    SOURCE_UNASSIGNED = "source_unassigned"
    SOURCE_UPDATED = "source_updated"


class ProjectAuditLog(SQLModel, table=True):
    """
    Audit trail for all project-related operations.
    Stores comprehensive logs for compliance monitoring per PROJ-006.
    """
    __tablename__ = "project_audit_log"
    
    # Primary Key
    log_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relationships
    project_id: Optional[int] = Field(default=None, foreign_key="project.project_id", index=True)
    jurisdiction_id: Optional[int] = Field(default=None, foreign_key="jurisdiction.jurisdiction_id", index=True)
    source_id: Optional[int] = Field(default=None, foreign_key="source.source_id", index=True)
    
    # Organization context (multi-tenancy)
    org_id: int = Field(foreign_key="organization.org_id", index=True, nullable=False)
    
    # Actor (who performed the action)
    user_id: int = Field(foreign_key="user.user_id", index=True, nullable=False)
    
    # Action type
    action: AuditAction = Field(max_length=100, index=True, nullable=False)
    
    # Change details (JSONB)
    details: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
        description="JSON object with before/after values, field changes, etc."
    )
    
    # Request context
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # ===== ROBUSTNESS HELPERS =====
    def __repr__(self):
        return (
            f"<ProjectAuditLog log_id={self.log_id} action={self.action} "
            f"project_id={self.project_id} user_id={self.user_id}>"
        )
    
    @classmethod
    def validate_action(cls, action: str) -> bool:
        """Return True if action is a valid AuditAction"""
        return action in AuditAction.__members__ or action in [a.value for a in AuditAction]

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": 1,
                "org_id": 1,
                "user_id": 10,
                "action": "project_created",
                "details": {
                    "title": "GDPR Compliance Monitoring",
                    "master_prompt": "Monitor GDPR changes..."
                },
                "ip_address": "192.168.1.1"
            }
        }
