from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.future import select

from app.api.modules.v1.notifications.models.ticket_notification import (
    TicketNotification,
    TicketNotificationStatus,
)
from app.api.modules.v1.notifications.service.ticket_notification_service import (
    send_ticket_notifications,
)
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketStatus
from app.api.modules.v1.users.models.users_model import User


# -------------------------------------------------------------------------
#  SUCCESSFUL EMAIL NOTIFICATION TEST
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ticket_notification_sends_emails_success(async_session):
    """
    Should send notifications to:
    - ticket creator
    - assigned user
    - project users
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()

    creator = User(id=uuid4(), email="creator@test.com")
    assignee = User(id=uuid4(), email="assignee@test.com")
    project_user = User(id=uuid4(), email="proj@test.com")

    async_session.add_all([creator, assignee, project_user])
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Test Ticket",
        status=TicketStatus.OPEN,
        created_by_user_id=creator.id,
        assigned_to_user_id=assignee.id,
        organization_id=org_id,
        project_id=project_id,
    )

    link = ProjectUser(project_id=project_id, user_id=project_user.id)

    async_session.add(ticket)
    async_session.add(link)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "Activity update")

    result = await async_session.execute(
        select(TicketNotification).where(TicketNotification.ticket_id == ticket_id)
    )

    rows = result.scalars().all()
    assert len(rows) == 3
    assert all(n.status == TicketNotificationStatus.SENT for n in rows)
    assert all(n.sent_at is not None for n in rows)


# -------------------------------------------------------------------------
#  IDEMPOTENCY TEST
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ticket_notification_idempotency(async_session):
    """
    If a SENT notification already exists, it should be skipped & not recreated.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()

    user = User(id=uuid4(), email="u@test.com")
    async_session.add(user)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Test",
        status=TicketStatus.OPEN,
        created_by_user_id=user.id,
        assigned_to_user_id=None,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    existing = TicketNotification(
        ticket_id=ticket_id,
        user_id=user.id,
        message="Activity update",
        status=TicketNotificationStatus.SENT,
        sent_at=datetime.now(timezone.utc),
    )

    async_session.add(existing)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "Activity update")

    result = await async_session.execute(
        select(TicketNotification).where(
            TicketNotification.ticket_id == ticket_id,
            TicketNotification.user_id == user.id,
        )
    )

    notifications = result.scalars().all()

    assert len(notifications) == 1
    assert notifications[0].status == TicketNotificationStatus.SENT


# -------------------------------------------------------------------------
#  EMAIL FAILURE TEST
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ticket_notification_email_failure(async_session):
    """
    Email sending fails → notification.status = FAILED
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()

    user = User(id=uuid4(), email="fail@test.com")
    async_session.add(user)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Test",
        status=TicketStatus.OPEN,
        created_by_user_id=user.id,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=False)):
        await send_ticket_notifications(str(ticket_id), "Activity")

    result = await async_session.execute(select(TicketNotification))
    notif = result.scalar_one()

    assert notif.status == TicketNotificationStatus.FAILED
    assert notif.sent_at is not None


# -------------------------------------------------------------------------
#  TICKET NOT FOUND TEST
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ticket_not_found(async_session):
    """
    If the ticket doesn't exist, no notifications should be created.
    """
    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock()):
        await send_ticket_notifications(str(uuid4()), "Msg")

    result = await async_session.execute(select(TicketNotification))
    rows = result.scalars().all()

    assert rows == []
