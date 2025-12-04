"""
Pydantic schemas for Project Audit Log API responses
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.modules.v1.projects.models.project_audit_log import AuditAction


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry"""

    log_id: int
    project_id: Optional[UUID]
    jurisdiction_id: Optional[UUID]
    source_id: Optional[UUID]
    org_id: UUID
    user_id: UUID
    action: AuditAction
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

    user_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "log_id": 123,
                "project_id": "550e8400-e29b-41d4-a716-446655440001",
                "org_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "action": "project_created",
                "details": {"title": "GDPR Monitoring", "master_prompt": "..."},
                "ip_address": "192.168.1.1",
                "created_at": "2025-11-20T10:00:00Z",
                "user_name": "John Doe",
                "user_email": "john@example.com",
            }
        }


class AuditLogListResponse(BaseModel):
    """Response schema for paginated audit logs"""

    data: List[AuditLogResponse]
    pagination: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "log_id": 123,
                        "project_id": "550e8400-e29b-41d4-a716-446655440001",
                        "action": "project_created",
                        "created_at": "2025-11-20T10:00:00Z",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "limit": 50,
                    "total_items": 145,
                    "total_pages": 3,
                },
            }
        }


class AuditLogQueryParams(BaseModel):
    """Query parameters for filtering audit logs"""

    action: Optional[AuditAction] = None
    user_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)


class AuditStatsResponse(BaseModel):
    """Statistics for audit logs (compliance reporting)"""

    total_logs: int
    by_action: Dict[str, int]
    by_user: Dict[str, int]
    date_range: Dict[str, datetime]

    class Config:
        json_schema_extra = {
            "example": {
                "total_logs": 1450,
                "by_action": {
                    "project_created": 120,
                    "jurisdiction_created": 450,
                    "source_assigned": 680,
                    "prompt_updated": 200,
                },
                "by_user": {
                    "123e4567-e89b-12d3-a456-426614174000": 500,
                    "550e8400-e29b-41d4-a716-446655440000": 350,
                },
                "date_range": {
                    "start": "2025-01-01T00:00:00Z",
                    "end": "2025-11-20T23:59:59Z",
                },
            }
        }
