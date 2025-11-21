# app/api/modules/v1/projects/routes/audit_routes.py 
"""
API endpoints for Project Audit Logs
Provides compliance monitoring and audit trail queries
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlmodel import Session
from typing import Optional
from datetime import datetime

from app.api.db.database import get_session
from app.api.modules.v1.projects.service.audit_service import ProjectAuditService
from app.api.modules.v1.projects.repositories.audit_repository import ProjectAuditRepository
from app.api.modules.v1.projects.schemas.audit_schemas import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditStatsResponse
)
from app.api.modules.v1.projects.models.project_audit_log import AuditAction

router = APIRouter(prefix="/audit", tags=["Project Audit"])

# ===== DEPENDENCY INJECTION =====

def get_audit_service(session: Session = Depends(get_session)) -> ProjectAuditService:
    """Dependency: Get audit service instance"""
    repository = ProjectAuditRepository(session)
    return ProjectAuditService(repository)


# TODO: Replace with actual auth dependency
def get_current_user():
    """Mock auth dependency - replace with actual implementation"""
    return {
        "user_id": 1,
        "org_id": 1,
        "role": "ADMIN",
        "email": "admin@example.com"
    }


# ===== ENDPOINTS =====

@router.get("/projects/{project_id}", response_model=AuditLogListResponse)
async def get_project_audit_logs(
    project_id: int,
    action: Optional[AuditAction] = None,
    user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get audit logs for a specific project"""
    logs, total = audit_service.repository.get_project_audit_logs(
        project_id=project_id,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit
    )

    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    pagination = {
        "page": page,
        "limit": limit,
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "has_next": page * limit < total,
        "has_prev": page > 1
    }

    return AuditLogListResponse(data=log_responses, pagination=pagination)


@router.get("/jurisdictions/{jurisdiction_id}", response_model=AuditLogListResponse)
async def get_jurisdiction_audit_logs(
    jurisdiction_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get audit logs for a specific jurisdiction"""
    logs, total = audit_service.repository.get_jurisdiction_audit_logs(
        jurisdiction_id=jurisdiction_id,
        page=page,
        limit=limit
    )

    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    pagination = {
        "page": page,
        "limit": limit,
        "total_items": total,
        "total_pages": (total + limit - 1) // limit
    }

    return AuditLogListResponse(data=log_responses, pagination=pagination)


@router.get("/organization", response_model=AuditLogListResponse)
async def get_organization_audit_logs(
    action: Optional[AuditAction] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get all audit logs for the current user's organization (Admin only)"""
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view organization-wide audit logs"
        )

    logs, total = audit_service.repository.get_organization_audit_logs(
        org_id=current_user["org_id"],
        action=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit
    )

    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    pagination = {
        "page": page,
        "limit": limit,
        "total_items": total,
        "total_pages": (total + limit - 1) // limit
    }

    return AuditLogListResponse(data=log_responses, pagination=pagination)


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log_by_id(
    log_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific audit log entry by ID"""
    from sqlmodel import select
    from app.api.modules.v1.projects.models.project_audit_log import ProjectAuditLog

    log = session.exec(
        select(ProjectAuditLog).where(
            ProjectAuditLog.log_id == log_id,
            ProjectAuditLog.org_id == current_user["org_id"]
        )
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogResponse.from_orm(log)


@router.get("/statistics", response_model=AuditStatsResponse)
async def get_audit_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get audit log statistics for compliance reporting (Admin only)"""
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view audit statistics"
        )

    from sqlmodel import select, func
    from app.api.modules.v1.projects.models.project_audit_log import ProjectAuditLog

    base_query = select(ProjectAuditLog).where(ProjectAuditLog.org_id == current_user["org_id"])
    if date_from:
        base_query = base_query.where(ProjectAuditLog.created_at >= date_from)
    if date_to:
        base_query = base_query.where(ProjectAuditLog.created_at <= date_to)

    total_logs = session.exec(select(func.count()).select_from(base_query.subquery())).one()

    # Stats by action
    by_action_results = session.exec(
        select(ProjectAuditLog.action, func.count(ProjectAuditLog.log_id))
        .where(ProjectAuditLog.org_id == current_user["org_id"])
        .group_by(ProjectAuditLog.action)
    ).all()
    by_action = {str(action): count for action, count in by_action_results}

    # Stats by user
    by_user_results = session.exec(
        select(ProjectAuditLog.user_id, func.count(ProjectAuditLog.log_id))
        .where(ProjectAuditLog.org_id == current_user["org_id"])
        .group_by(ProjectAuditLog.user_id)
    ).all()
    by_user = {str(user_id): count for user_id, count in by_user_results}

    date_range = {}
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


@router.get("/export", status_code=200)
async def export_audit_logs(
    format: str = Query("csv", regex="^(csv|json)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Export audit logs for compliance reporting (Admin only)"""
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can export audit logs"
        )

    logs, _ = audit_service.repository.get_organization_audit_logs(
        org_id=current_user["org_id"],
        date_from=date_from,
        date_to=date_to,
        page=1,
        limit=10000  # Max export
    )

    if format == "csv":
        import csv
        from io import StringIO
        from fastapi.responses import StreamingResponse

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "log_id", "project_id", "jurisdiction_id", "source_id",
            "user_id", "action", "details", "ip_address", "created_at"
        ])
        for log in logs:
            writer.writerow([
                log.log_id,
                log.project_id or "",
                log.jurisdiction_id or "",
                log.source_id or "",
                log.user_id,
                log.action,
                str(log.details) if log.details else "",
                log.ip_address or "",
                log.created_at.isoformat()
            ])
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )

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
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
        return JSONResponse(content={"logs": logs_data})
