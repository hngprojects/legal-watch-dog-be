"""
API endpoints for Project Audit Logs
Provides compliance monitoring and audit trail queries
"""

import csv
from datetime import datetime
from io import StringIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import (
    get_current_user,
    require_permission,
)
from app.api.db.database import get_db as get_session
from app.api.modules.v1.projects.models.project_audit_log import AuditAction
from app.api.modules.v1.projects.repositories.audit_repository import (
    ProjectAuditRepository,
)
from app.api.modules.v1.projects.schemas.audit_schemas import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditStatsResponse,
)
from app.api.modules.v1.projects.services.audit_service import ProjectAuditService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.permissions import Permission

router = APIRouter(prefix="/projects/audit", tags=["Audit"])


# DEPENDENCY INJECTION


def get_audit_service(
    session: AsyncSession = Depends(get_session),
) -> ProjectAuditService:
    repository = ProjectAuditRepository(session)
    return ProjectAuditService(repository)


# ENDPOINTS


@router.get("/jurisdictions/{jurisdiction_id}", response_model=AuditLogListResponse)
async def get_jurisdiction_audit_logs(
    jurisdiction_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """Get audit logs for a specific jurisdiction"""
    logs, total = await audit_service.get_jurisdiction_audit_logs(
        jurisdiction_id=jurisdiction_id, page=page, limit=limit
    )

    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    pagination = {
        "page": page,
        "limit": limit,
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
    }

    return AuditLogListResponse(data=log_responses, pagination=pagination)


@router.get("/organization", response_model=AuditLogListResponse)
async def get_organization_audit_logs(
    action: Optional[AuditAction] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """Get all audit logs for the current user's organization (requires VIEW_AUDIT permission)"""
    logs, total = await audit_service.get_organization_audit_logs(
        org_id=current_user.organization_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )

    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    pagination = {
        "page": page,
        "limit": limit,
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
    }

    return AuditLogListResponse(data=log_responses, pagination=pagination)


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log_by_id(
    log_id: int,
    current_user: User = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """Get a specific audit log entry by ID via service layer"""

    log = await audit_service.get_audit_log_by_id(
        log_id=log_id, org_id=current_user.organization_id
    )

    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogResponse.from_orm(log)


@router.get("/statistics", response_model=AuditStatsResponse)
async def get_audit_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """Get audit log statistics for compliance reporting (Admin only)"""
    return await audit_service.get_audit_statistics(
        org_id=current_user.organization_id, date_from=date_from, date_to=date_to
    )


@router.get("/export", status_code=200)
async def export_audit_logs(
    format: str = Query("csv", pattern="^(csv|json)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """Export audit logs for compliance reporting (Admin only)"""
    logs, _ = await audit_service.get_organization_audit_logs(
        org_id=current_user.organization_id,
        date_from=date_from,
        date_to=date_to,
        page=1,
        limit=10000,  # Max export
    )

    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "log_id",
                "project_id",
                "jurisdiction_id",
                "source_id",
                "user_id",
                "action",
                "details",
                "ip_address",
                "created_at",
            ]
        )

        for log in logs:
            writer.writerow(
                [
                    log.log_id,
                    log.project_id or "",
                    log.jurisdiction_id or "",
                    log.source_id or "",
                    log.user_id,
                    log.action,
                    str(log.details) if log.details else "",
                    log.ip_address or "",
                    log.created_at.isoformat(),
                ]
            )

        output.seek(0)

        filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}

        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)

    else:  # JSON
        from fastapi.responses import JSONResponse

        logs_data = [
            {
                "log_id": log.log_id,
                "project_id": log.project_id,
                "jurisdiction_id": log.jurisdiction_id,
                "source_id": log.source_id,
                "user_id": log.user_id,
                "action": log.action,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
        return JSONResponse(content={"logs": logs_data})


@router.get("/{project_id}", response_model=AuditLogListResponse)
async def get_project_audit_logs(
    project_id: UUID,
    action: Optional[AuditAction] = None,
    user_id: Optional[UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """Get audit logs for a specific project"""
    logs, total = await audit_service.get_project_audit_logs(
        project_id=project_id,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )

    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    pagination = {
        "page": page,
        "limit": limit,
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "has_next": page * limit < total,
        "has_prev": page > 1,
    }

    return AuditLogListResponse(data=log_responses, pagination=pagination)
