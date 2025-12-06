from fastapi import APIRouter, BackgroundTasks

from app.api.modules.v1.notifications.service.ticket_notification_service import (
    send_ticket_notifications,
)

router = APIRouter(prefix="/notifications/tickets", tags=["Notifications"])


@router.post("/{ticket_id}/send")
async def trigger_ticket_notification(
    ticket_id: str, message: str, background_tasks: BackgroundTasks
):
    # Use FastAPI's BackgroundTasks instead of Celery for now
    background_tasks.add_task(send_ticket_notifications, ticket_id, message)
    return {"detail": "Notification task queued"}
