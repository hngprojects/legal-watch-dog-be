from fastapi import APIRouter

from app.api.modules.v1.notifications.service.ticket_notification_service import (
    send_ticket_notifications_task,
)

router = APIRouter(prefix="/notifications/tickets", tags=["Notifications"])


@router.post("/{ticket_id}/send")
async def trigger_ticket_notification(ticket_id: str, message: str):
    send_ticket_notifications_task.delay(ticket_id, message)
    return {"detail": "Notification task queued"}
