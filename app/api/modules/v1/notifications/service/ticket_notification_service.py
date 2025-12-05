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


async def send_ticket_notifications(ticket_id: str, activity_message: str, session=None):
    """
    Sends notifications to all users associated with a ticket.
    Supports test session injection (session fixture) to allow CI tests to pass.
    """
    own_session = False
    try:
        # Use the test session if provided, else create a new DB session
        if session is None:
            session = AsyncSessionLocal()
            own_session = True

        ticket_uuid = UUID(ticket_id)

        # Fetch ticket
        ticket_result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_uuid)
        )
        ticket = ticket_result.scalar_one_or_none()

        if not ticket:
            logger.warning(f"No ticket found with id {ticket_id}")
            return

        # Fetch project users
        project_users_result = await session.execute(
            select(ProjectUser).where(ProjectUser.project_id == ticket.project_id)
        )
        project_users = project_users_result.scalars().all()

        user_ids = {ticket.created_by_user_id}

        if ticket.assigned_to_user_id:
            user_ids.add(ticket.assigned_to_user_id)

        user_ids.update({pu.user_id for pu in project_users})

        for user_id in user_ids:
            # Fetch user
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            # IDEMPOTENCY CHECK
            existing_result = await session.execute(
                select(TicketNotification).where(
                    TicketNotification.ticket_id == ticket_uuid,
                    TicketNotification.user_id == user.id,
                    TicketNotification.message == activity_message,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing and existing.status == TicketNotificationStatus.SENT:
                # Already sent → skip (expected by tests)
                continue

            if existing:
                notification = existing
            else:
                # Create notification
                notification = TicketNotification(
                    ticket_id=ticket_uuid,
                    user_id=user.id,
                    message=activity_message,
                )
                session.add(notification)
                # no commit yet — wait until after send_email

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

            except Exception as e:
                notification.status = TicketNotificationStatus.FAILED
                notification.sent_at = datetime.now(timezone.utc)
                logger.error(f"Error sending ticket notification: {str(e)}")

            # Commit after each update
            await session.commit()

    except SQLAlchemyError as exc:
        logger.error(f"DB Error (Ticket Notifications): {str(exc)}")
        raise

    finally:
        if own_session:
            await session.close()
