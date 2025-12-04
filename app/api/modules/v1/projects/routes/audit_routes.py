"""
API endpoints for Project Audit Logs
Provides compliance monitoring and audit trail queries

This module mirrors the structure, dependency injection, error handling,
logging and response formatting used in auth_routes.py: all endpoints return
standardized JSON via success_response / error_response and accept db via
Depends(get_db).
"""

import csv
import logging
from datetime import datetime
from io import StringIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user, require_permission
from app.api.db.database import get_db
from app.api.modules.v1.projects.models.project_audit_log import AuditAction
from app.api.modules.v1.projects.repositories.audit_repository import ProjectAuditRepository
from app.api.modules.v1.projects.schemas.audit_schemas import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditStatsResponse,
)
from app.api.modules.v1.projects.services.audit_service import ProjectAuditService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.permissions import Permission
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger("app")

router = APIRouter(prefix="/projects/{project_id}/audit", tags=["Audit"])


def get_audit_service(session: AsyncSession = Depends(get_db)) -> ProjectAuditService:
    """
    Dependency injector for the audit service.

    Args:
        session (AsyncSession): Database session injected from get_db.

    Returns:
        ProjectAuditService: Service instance wrapping repository.
    """
    repository = ProjectAuditRepository(session)
    return ProjectAuditService(repository)


@router.get("/jurisdictions/{jurisdiction_id}", response_model=AuditLogListResponse)
async def get_jurisdiction_audit_logs(
    jurisdiction_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """
    Get audit logs for a specific jurisdiction.

    Args:
        jurisdiction_id (UUID): jurisdiction to query logs for.
        page (int): page number (default 1).
        limit (int): items per page (default 50).
        current_user (User): current authenticated user.
        audit_service (ProjectAuditService): injected service.

    Returns:
        JSONResponse: standardized success_response containing:
            data: {
                "results": [<audit log dicts>],
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages
            }
    """
    try:
        logs, total = await audit_service.get_jurisdiction_audit_logs(
            jurisdiction_id=jurisdiction_id, page=page, limit=limit
        )

        results = [AuditLogResponse.model_validate(log).model_dump() for log in logs]
        total_pages = (total + limit - 1) // limit

        payload = {
            "results": results,
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": total_pages,
        }

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Jurisdiction audit logs retrieved successfully",
            data=payload,
        )

    except SQLAlchemyError as e:
        logger.exception("Database error fetching jurisdiction audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve jurisdiction audit logs.",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching jurisdiction audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve jurisdiction audit logs.",
        )


@router.get("/organizations", response_model=AuditLogListResponse)
async def get_organization_audit_logs(
    action: Optional[AuditAction] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """
    Get all audit logs for the current user's organization (requires VIEW_AUDIT permission).

    Args:
        action (Optional[AuditAction]): optional filter by action.
        date_from (Optional[datetime]): start datetime filter.
        date_to (Optional[datetime]): end datetime filter.
        page (int): pagination page.
        limit (int): items per page.
        current_user (User): current authenticated user with permission.
        audit_service (ProjectAuditService): injected service.

    Returns:
        JSONResponse: standardized success_response with paginated logs.
    """
    try:
        logs, total = await audit_service.get_organization_audit_logs(
            org_id=current_user.organization_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )

        results = [AuditLogResponse.model_validate(log).model_dump() for log in logs]
        total_pages = (total + limit - 1) // limit
        payload = {
            "results": results,
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": total_pages,
        }

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization audit logs retrieved successfully",
            data=payload,
        )

    except SQLAlchemyError as e:
        logger.exception("Database error fetching organization audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organization audit logs.",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching organization audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organization audit logs.",
        )


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log_by_id(
    log_id: int,
    current_user: User = Depends(get_current_user),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """
    Get a specific audit log entry by ID via service layer.

    Args:
        log_id (int): integer id of the audit log.
        current_user (User): current authenticated user.
        audit_service (ProjectAuditService): injected service.

    Returns:
        JSONResponse: success_response with the audit log data or 404 error_response.
    """
    try:
        log = await audit_service.get_audit_log_by_id(
            log_id=log_id, org_id=current_user.organization_id
        )

        if not log:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Audit log not found",
            )

        data = AuditLogResponse.model_validate(log).model_dump()
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Audit log retrieved successfully",
            data=data,
        )

    except SQLAlchemyError as e:
        logger.exception("Database error fetching audit log by id: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve audit log.",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching audit log by id: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve audit log.",
        )


@router.get("/statistics", response_model=AuditStatsResponse)
async def get_audit_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """
    Get audit log statistics for compliance reporting (Admin only).

    Args:
        date_from (Optional[datetime]): start datetime filter.
        date_to (Optional[datetime]): end datetime filter.
        current_user (User): authenticated user (must have VIEW_AUDIT).
        audit_service (ProjectAuditService): injected service.

    Returns:
        JSONResponse: success_response with statistics payload or error_response.
    """
    try:
        stats = await audit_service.get_audit_statistics(
            org_id=current_user.organization_id, date_from=date_from, date_to=date_to
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Audit statistics retrieved successfully",
            data=stats,
        )

    except SQLAlchemyError as e:
        logger.exception("Database error fetching audit statistics: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve audit statistics.",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching audit statistics: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve audit statistics.",
        )


@router.get("/exports", status_code=status.HTTP_200_OK)
async def export_audit_logs(
    format: str = Query("csv", pattern="^(csv|json)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
    audit_service: ProjectAuditService = Depends(get_audit_service),
):
    """
    Export audit logs for compliance reporting (Admin only).

    Supports CSV and JSON export. Returns StreamingResponse for CSV and JSONResponse
    for JSON. Errors are returned via standardized error_response.

    Args:
        format (str): 'csv' or 'json' (default 'csv').
        date_from (Optional[datetime]): start filter.
        date_to (Optional[datetime]): end filter.
        current_user (User): authenticated user with VIEW_AUDIT.
        audit_service (ProjectAuditService): injected service.

    Returns:
        StreamingResponse or JSONResponse with the exported data, or error_response on failure.
    """
    try:
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

            return StreamingResponse(
                iter([output.getvalue()]), media_type="text/csv", headers=headers
            )

        else:
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

    except SQLAlchemyError as e:
        logger.exception("Database error exporting audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to export audit logs.",
        )
    except Exception as e:
        logger.exception("Unexpected error exporting audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to export audit logs.",
        )


@router.get("/", response_model=AuditLogListResponse)
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
    """
    Get audit logs for a specific project.

    Args:
        project_id (UUID): project to query logs for.
        action (Optional[AuditAction]): optional action filter.
        user_id (Optional[UUID]): optional user filter.
        date_from (Optional[datetime]): start filter.
        date_to (Optional[datetime]): end filter.
        page (int): page number.
        limit (int): items per page.
        current_user (User): authenticated user.
        audit_service (ProjectAuditService): injected service.

    Returns:
        JSONResponse: success_response with paginated list or error_response.
    """
    try:
        logs, total = await audit_service.get_project_audit_logs(
            project_id=project_id,
            action=action,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )

        results = [AuditLogResponse.model_validate(log).model_dump() for log in logs]
        total_pages = (total + limit - 1) // limit
        payload = {
            "results": results,
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page * limit < total,
            "has_prev": page > 1,
        }

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project audit logs retrieved successfully",
            data=payload,
        )

    except SQLAlchemyError as e:
        logger.exception("Database error fetching project audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project audit logs.",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching project audit logs: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project audit logs.",
        )
