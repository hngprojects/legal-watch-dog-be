from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import desc, func
from sqlalchemy.future import select

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import AsyncSession, get_db
from app.api.modules.v1.notifications.models.ticket_notification import TicketNotification
from app.api.modules.v1.notifications.schemas.notification_schema import (
    TicketNotificationListResponse,
    TicketNotificationResponse,
)
from app.api.modules.v1.notifications.service.ticket_notification_service import (
    send_ticket_notifications,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

router = APIRouter(prefix="/notifications/tickets", tags=["Notifications"])


@router.post("/{ticket_id}/send")
async def trigger_ticket_notification(
    ticket_id: str, message: str, background_tasks: BackgroundTasks
):
    # Use FastAPI's BackgroundTasks instead of Celery for now
    background_tasks.add_task(send_ticket_notifications, ticket_id, message)
    return {"detail": "Notification task queued"}


@router.get("", response_model=TicketNotificationListResponse)
async def get_ticket_notifications(
    limit: int = 10,
    page: int = 1,
    is_read: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated ticket notifications for the current user.
    """
    offset = (page - 1) * limit

    # Base query for user's notifications
    query = select(TicketNotification).where(TicketNotification.user_id == current_user.id)

    # Filter by read status if provided
    if is_read is not None:
        query = query.where(TicketNotification.is_read == is_read)

    # Count total matching
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    # Count unread for this user (global unread count)
    unread_result = await db.execute(
        select(func.count())
        .select_from(TicketNotification)
        # .where(TicketNotification.user_id == current_user.id, TicketNotification.is_read == False)
        .where(
            TicketNotification.user_id == current_user.id,
            not TicketNotification.is_read
        )

    )
    unread_count = unread_result.scalar_one()

    # Fetch paginated results
    query = query.order_by(desc(TicketNotification.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()

    return success_response(
        data={
            "notifications": notifications,
            "total": total,
            "page": page,
            "limit": limit,
            "unread_count": unread_count,
        }
    )


@router.patch("/{notification_id}/read", response_model=TicketNotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a ticket notification as read.
    """
    result = await db.execute(
        select(TicketNotification).where(
            TicketNotification.notification_id == notification_id,
            TicketNotification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        return success_response(status_code=404, message="Notification not found")

    from datetime import datetime, timezone

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notification)

    return success_response(data=notification)
