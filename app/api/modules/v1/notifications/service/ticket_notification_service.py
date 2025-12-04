import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.api.core.dependencies.send_mail import send_email
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.notifications.models.ticket_notification import (
    TicketNotification,
    TicketNotificationStatus,
)
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.tickets.models.ticket_model import Ticket
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


async def send_ticket_notifications(ticket_id: str, activity_message: str):
    """
    Sends notifications to all users involved in a ticket:
    - creator
    - assigned user
    - all project users (optional)
    """

    try:
        async with AsyncSessionLocal() as session:
            ticket_uuid = UUID(ticket_id)

            ticket_result = await session.execute(select(Ticket).where(Ticket.id == ticket_uuid))
            ticket = ticket_result.scalar_one_or_none()

            if not ticket:
                logger.warning(f"No ticket found with id {ticket_id}")
                return

            # Get participants: creator, assignee, and project users
            project_users_result = await session.execute(
                select(ProjectUser).where(ProjectUser.project_id == ticket.project_id)
            )
            project_users = project_users_result.scalars().all()

            user_ids = {ticket.created_by_user_id}

            if ticket.assigned_to_user_id:
                user_ids.add(ticket.assigned_to_user_id)

            user_ids.update({pu.user_id for pu in project_users})

            notifications_sent = 0
            notifications_failed = 0
            notifications_skipped = 0

            for user_id in user_ids:
                user_result = await session.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()
                if not user:
                    continue

                # Idempotency: prevent duplicates
                existing_result = await session.execute(
                    select(TicketNotification).where(
                        TicketNotification.ticket_id == ticket_uuid,
                        TicketNotification.user_id == user.id,
                        TicketNotification.message == activity_message,
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    if existing.status == TicketNotificationStatus.SENT:
                        notifications_skipped += 1
                        continue
                    notification = existing
                else:
                    notification = TicketNotification(
                        ticket_id=ticket_uuid,
                        user_id=user.id,
                        message=activity_message,
                    )
                    session.add(notification)
                    await session.commit()
                    await session.refresh(notification)

                # Try sending email
                try:
                    success = await send_email(
                        template_name="ticket_notification.html",
                        subject=f"Ticket Update: {ticket.title}",
                        recipient=user.email,
                        context={
                            "ticket_title": ticket.title,
                            "message": activity_message,
                            "status": ticket.status,
                        },
                    )

                    notification.status = (
                        TicketNotificationStatus.SENT
                        if success
                        else TicketNotificationStatus.FAILED
                    )
                    notification.sent_at = datetime.now(timezone.utc)
                    await session.commit()

                    if success:
                        notifications_sent += 1
                    else:
                        notifications_failed += 1

                except Exception as e:
                    notification.status = TicketNotificationStatus.FAILED
                    await session.commit()
                    notifications_failed += 1
                    logger.error(f"Error sending ticket notification: {str(e)}")

            logger.info(
                f"Ticket {ticket_id} notif summary → Sent: {notifications_sent}, "
                f"Failed: {notifications_failed}, Skipped: {notifications_skipped}"
            )

    except SQLAlchemyError as exc:
        logger.error(f"DB Error (Ticket Notifications): {str(exc)}")
        raise
