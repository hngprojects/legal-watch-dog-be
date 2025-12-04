import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.notifications.schemas.notification_schema import (
    NotificationContextResponse,
    NotificationFilter,
    NotificationListResponse,
    NotificationMarkRead,
    NotificationResponse,
    NotificationStats,
    NotificationUpdate,
)
from app.api.modules.v1.notifications.service.notification_service import (
    NotificationService,
)
from app.api.modules.v1.users.models.users_model import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=NotificationListResponse, summary="Get user notifications")
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    organization_id: Optional[uuid.UUID] = Query(None, description="Filter by organization"),
    source_id: Optional[uuid.UUID] = Query(None, description="Filter by source"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get notifications for the current user with pagination and filters.
    """

    user_id = current_user.id

    filters = NotificationFilter(
        status=status,
        notification_type=notification_type,
        is_read=is_read,
        organization_id=organization_id,
        source_id=source_id,
    )

    skip = (page - 1) * page_size
    notifications, total = await NotificationService.get_user_notifications(
        db=db, user_id=user_id, filters=filters, skip=skip, limit=page_size
    )

    unread_count = await NotificationService.get_unread_count(db, user_id)

    return NotificationListResponse(
        notifications=notifications,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


@router.get(
    "/{notification_id}", response_model=NotificationResponse, summary="Get notification by ID"
)
async def get_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific notification by ID."""

    user_id = current_user.id

    notification = await NotificationService.get_notification_by_id(db, notification_id, user_id)

    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return notification


@router.get(
    "/{notification_id}/context",
    response_model=NotificationContextResponse,
    summary="Get notification with full context",
)
async def get_notification_with_context(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get notification with full context including related entities.

    This endpoint provides all the context needed to navigate directly
    to the relevant revision, project, source, etc.
    """

    user_id = current_user.id

    context = await NotificationService.get_notification_with_context(db, notification_id, user_id)

    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return context


@router.patch(
    "/{notification_id}", response_model=NotificationResponse, summary="Update notification"
)
async def update_notification(
    notification_id: uuid.UUID,
    update_data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a notification (e.g., mark as read)."""

    user_id = current_user.id

    notification = await NotificationService.update_notification(
        db, notification_id, user_id, update_data
    )

    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return notification


@router.post("/mark-read", status_code=status.HTTP_200_OK, summary="Mark notifications as read")
async def mark_notifications_read(
    mark_data: NotificationMarkRead,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark one or more notifications as read."""

    user_id = current_user.id

    count = await NotificationService.mark_as_read(db, mark_data.notification_ids, user_id)

    return {"message": f"Marked {count} notification(s) as read", "count": count}


@router.post(
    "/mark-all-read", status_code=status.HTTP_200_OK, summary="Mark all notifications as read"
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Mark all unread notifications as read for the current user."""

    user_id = current_user.id

    count = await NotificationService.mark_all_as_read(db, user_id)

    return {"message": f"Marked {count} notification(s) as read", "count": count}


@router.delete(
    "/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete notification"
)
async def delete_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a notification."""

    user_id = current_user.id

    deleted = await NotificationService.delete_notification(db, notification_id, user_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return None


@router.get("/stats", response_model=NotificationStats, summary="Get notification statistics")
async def get_notification_stats(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get statistics about the current user's notifications."""

    user_id = current_user.id

    stats = await NotificationService.get_notification_stats(db, user_id)

    return stats
