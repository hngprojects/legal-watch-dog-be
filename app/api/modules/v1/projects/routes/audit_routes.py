# app/api/modules/v1/projects/routes/audit_routes.py
"""
API endpoints for Project Audit Logs
Provides compliance monitoring and audit trail queries
"""

import csv
import os
from datetime import datetime
from io import StringIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db as get_session
from app.api.modules.v1.projects.models.project_audit_log import AuditAction
from app.api.modules.v1.projects.repositories.audit_repository import ProjectAuditRepository
from app.api.modules.v1.projects.schemas.audit_schemas import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditStatsResponse,
)
from app.api.modules.v1.projects.services.audit_service import ProjectAuditService

router = APIRouter(tags=["Audit"])


# ===== DEPENDENCY INJECTION =====

def get_audit_service(session: AsyncSession = Depends(get_session)) -> ProjectAuditService:
    repository = ProjectAuditRepository(session)
    return ProjectAuditService(repository)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  # your login endpoint

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    JWT_SECRET = os.getenv("JWT_SECRET")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

    if not JWT_SECRET or not JWT_ALGORITHM:
        raise RuntimeError("JWT_SECRET and JWT_ALGORITHM must be set in environment")

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )    
        user_id: str = payload.get("user_id")
        org_id: str = payload.get("org_id")
        role: str = payload.get("role")
        email: str = payload.get("email")
        if not user_id or not org_id:
            raise credentials_exception
        return {
            "user_id": UUID(user_id),
            "org_id": UUID(org_id),
            "role": role,
            "email": email
        }
    except JWTError:
        raise credentials_exception

# ===== ENDPOINTS =====

@router.get("/projects/{project_id}", response_model=AuditLogListResponse)
async def get_project_audit_logs(
    project_id: UUID,
    action: Optional[AuditAction] = None,
    user_id: Optional[UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get audit logs for a specific project"""
    logs, total = await audit_service.get_project_audit_logs(
        
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
    jurisdiction_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get audit logs for a specific jurisdiction"""
    logs, total = await audit_service.get_jurisdiction_audit_logs(
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

    logs, total = await audit_service.get_organization_audit_logs(
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
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get a specific audit log entry by ID via service layer"""

    log = await audit_service.get_audit_log_by_id(
        log_id=log_id,
        org_id=current_user["org_id"]
    )

    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogResponse.from_orm(log)



@router.get("/statistics", response_model=AuditStatsResponse)
async def get_audit_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict[str, UUID | str] = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Get audit log statistics for compliance reporting (Admin only)"""
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view audit statistics"
        )

    return await audit_service.get_audit_statistics(
        org_id=current_user["org_id"],
        date_from=date_from,
        date_to=date_to
    )


@router.get("/export", status_code=200)
async def export_audit_logs(
    format: str = Query("csv", pattern="^(csv|json)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: dict[str, UUID | str] = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service)
):
    """Export audit logs for compliance reporting (Admin only)"""
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can export audit logs"
        )

    logs, _ = await audit_service.get_organization_audit_logs(
        org_id=current_user["org_id"],
        date_from=date_from,
        date_to=date_to,
        page=1,
        limit=10000  # Max export
    )

    if format == "csv":

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

        # Create filename and headers separately to shorten line length
        filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers=headers
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
