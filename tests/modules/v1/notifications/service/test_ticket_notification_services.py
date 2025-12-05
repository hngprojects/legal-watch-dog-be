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
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketStatus
from app.api.modules.v1.users.models.users_model import User


# =========================================================================
#  FIXTURES
# =========================================================================
@pytest.fixture
def async_session(pg_async_session):
    """
    Local alias fixture to satisfy tests using `async_session`.
    """
    return pg_async_session


# =========================================================================
#  SUCCESSFUL NOTIFICATION TESTS
# =========================================================================
@pytest.mark.asyncio
async def test_ticket_notification_sends_emails_success(async_session):
    """
    Test that notifications are successfully sent to all relevant users:
    - Ticket creator
    - Assigned user
    - Project users

    Verifies that all notifications are created with SENT status and sent_at timestamp.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    creator = User(id=uuid4(), email="creator@test.com", name="Creator User")
    assignee = User(id=uuid4(), email="assignee@test.com", name="Assignee User")
    project_user = User(id=uuid4(), email="proj@test.com", name="Project User")

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
        await send_ticket_notifications(str(ticket_id), "Activity update", session=async_session)

    result = await async_session.execute(
        select(TicketNotification).where(TicketNotification.ticket_id == ticket_id)
    )

    rows = result.scalars().all()
    assert len(rows) == 3
    assert all(n.status == TicketNotificationStatus.SENT for n in rows)
    assert all(n.sent_at is not None for n in rows)
    assert all(n.message == "Activity update" for n in rows)


@pytest.mark.asyncio
async def test_ticket_notification_only_creator(async_session):
    """
    Test notification when ticket has only a creator (no assignee or project users).

    Verifies that a single notification is sent to the creator.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    creator = User(id=uuid4(), email="creator@test.com")
    async_session.add(creator)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Solo Ticket",
        status=TicketStatus.OPEN,
        created_by_user_id=creator.id,
        assigned_to_user_id=None,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "New ticket created", session=async_session)

    result = await async_session.execute(
        select(TicketNotification).where(TicketNotification.ticket_id == ticket_id)
    )

    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == creator.id
    assert rows[0].status == TicketNotificationStatus.SENT


@pytest.mark.asyncio
async def test_ticket_notification_multiple_project_users(async_session):
    """
    Test notification with multiple project users.

    Verifies that all project users receive notifications along with creator and assignee.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    creator = User(id=uuid4(), email="creator@test.com", name="Creator User")
    assignee = User(id=uuid4(), email="assignee@test.com", name="Assignee User")
    project_user1 = User(id=uuid4(), email="proj1@test.com", name="Project User 1")
    project_user2 = User(id=uuid4(), email="proj2@test.com", name="Project User 2")
    project_user3 = User(id=uuid4(), email="proj3@test.com", name="Project User 3")

    async_session.add_all([creator, assignee, project_user1, project_user2, project_user3])
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Multi-User Ticket",
        status=TicketStatus.IN_PROGRESS,
        created_by_user_id=creator.id,
        assigned_to_user_id=assignee.id,
        organization_id=org_id,
        project_id=project_id,
    )

    # Add multiple project users
    links = [
        ProjectUser(project_id=project_id, user_id=project_user1.id),
        ProjectUser(project_id=project_id, user_id=project_user2.id),
        ProjectUser(project_id=project_id, user_id=project_user3.id),
    ]

    async_session.add(ticket)
    async_session.add_all(links)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "Status updated", session=async_session)

    result = await async_session.execute(
        select(TicketNotification).where(TicketNotification.ticket_id == ticket_id)
    )

    rows = result.scalars().all()
    # Should have 5 notifications: creator, assignee, and 3 project users
    assert len(rows) == 5

    user_ids = {n.user_id for n in rows}
    expected_ids = {creator.id, assignee.id, project_user1.id, project_user2.id, project_user3.id}
    assert user_ids == expected_ids


@pytest.mark.asyncio
async def test_ticket_notification_duplicate_user_handling(async_session):
    """
    Test that duplicate users (e.g., creator is also a project user) receive only one notification.

    Verifies deduplication logic works correctly.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    creator = User(id=uuid4(), email="creator@test.com")
    async_session.add(creator)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Duplicate User Ticket",
        status=TicketStatus.OPEN,
        created_by_user_id=creator.id,
        assigned_to_user_id=creator.id,  # Creator is also assignee
        organization_id=org_id,
        project_id=project_id,
    )

    # Creator is also a project user
    link = ProjectUser(project_id=project_id, user_id=creator.id)

    async_session.add(ticket)
    async_session.add(link)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "Update", session=async_session)

    result = await async_session.execute(
        select(TicketNotification).where(TicketNotification.ticket_id == ticket_id)
    )

    rows = result.scalars().all()
    # Should only have 1 notification despite user being creator, assignee, and project user
    assert len(rows) == 1
    assert rows[0].user_id == creator.id


# =========================================================================
#  IDEMPOTENCY TESTS
# =========================================================================
@pytest.mark.asyncio
async def test_ticket_notification_idempotency(async_session):
    """
    Test that already-sent notifications are not resent.

    Verifies idempotency: if a SENT notification exists for the same ticket,
    user, and message, it should not be recreated or resent.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="u@test.com", name="Test User")
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

    with patch(
        "app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)
    ) as mock_email:
        await send_ticket_notifications(str(ticket_id), "Activity update", session=async_session)

        # Email should not be called since notification already sent
        mock_email.assert_not_called()

    result = await async_session.execute(
        select(TicketNotification).where(
            TicketNotification.ticket_id == ticket_id,
            TicketNotification.user_id == user.id,
        )
    )

    notifications = result.scalars().all()
    assert len(notifications) == 1
    assert notifications[0].status == TicketNotificationStatus.SENT


@pytest.mark.asyncio
async def test_ticket_notification_retry_failed(async_session):
    """
    Test that FAILED notifications can be retried with a new message.

    Verifies that a failed notification with a different message creates a new notification.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="retry@test.com", name="Retry User")
    async_session.add(user)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Retry Test",
        status=TicketStatus.OPEN,
        created_by_user_id=user.id,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    # Create a failed notification
    failed_notif = TicketNotification(
        ticket_id=ticket_id,
        user_id=user.id,
        message="First attempt",
        status=TicketNotificationStatus.FAILED,
        sent_at=datetime.now(timezone.utc),
    )

    async_session.add(failed_notif)
    await async_session.commit()

    # Try sending with a different message
    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "Second attempt", session=async_session)

    result = await async_session.execute(
        select(TicketNotification).where(TicketNotification.ticket_id == ticket_id)
    )

    notifications = result.scalars().all()
    # Should have 2 notifications: the failed one and the new successful one
    assert len(notifications) == 2

    messages = {n.message for n in notifications}
    assert messages == {"First attempt", "Second attempt"}


# =========================================================================
#  ERROR HANDLING TESTS
# =========================================================================
@pytest.mark.asyncio
async def test_ticket_notification_email_failure(async_session):
    """
    Test that notification status is set to FAILED when email sending fails.

    Verifies proper error handling when send_email returns False.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="fail@test.com", name="Fail User")
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
        await send_ticket_notifications(str(ticket_id), "Activity", session=async_session)

    result = await async_session.execute(select(TicketNotification))
    notif = result.scalar_one()

    assert notif.status == TicketNotificationStatus.FAILED
    assert notif.sent_at is not None


@pytest.mark.asyncio
async def test_ticket_notification_email_exception(async_session):
    """
    Test that notification status is set to FAILED when email sending raises an exception.

    Verifies proper exception handling in the notification service.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="exception@test.com", name="Exception User")
    async_session.add(user)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Exception Test",
        status=TicketStatus.OPEN,
        created_by_user_id=user.id,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    with patch(
        "app.api.core.dependencies.send_mail.send_email",
        new=AsyncMock(side_effect=Exception("SMTP error")),
    ):
        await send_ticket_notifications(str(ticket_id), "Test message", session=async_session)

    result = await async_session.execute(select(TicketNotification))
    notif = result.scalar_one()

    assert notif.status == TicketNotificationStatus.FAILED
    assert notif.sent_at is not None


@pytest.mark.asyncio
async def test_ticket_not_found(async_session):
    """
    Test that no notifications are created when ticket doesn't exist.

    Verifies graceful handling of non-existent ticket IDs.
    """
    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock()):
        await send_ticket_notifications(str(uuid4()), "Msg", session=async_session)

    result = await async_session.execute(select(TicketNotification))
    rows = result.scalars().all()

    assert rows == []


@pytest.mark.asyncio
async def test_ticket_notification_missing_user(async_session):
    """
    Test that notifications are skipped for users that don't exist.

    Verifies that the service handles missing user records gracefully.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    # Create a user that we'll reference but then delete
    temp_user = User(id=uuid4(), email="temp@test.com", name="Temp User")
    async_session.add(temp_user)
    await async_session.commit()

    user_id = temp_user.id

    # Delete the user
    await async_session.delete(temp_user)
    await async_session.commit()

    # Create ticket referencing the deleted user
    ticket = Ticket(
        id=ticket_id,
        title="Missing User Test",
        status=TicketStatus.OPEN,
        created_by_user_id=user_id,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        # Should not raise an error
        await send_ticket_notifications(str(ticket_id), "Test", session=async_session)

    result = await async_session.execute(select(TicketNotification))
    rows = result.scalars().all()

    # No notifications should be created since user doesn't exist
    assert len(rows) == 0


# =========================================================================
#  VALIDATION TESTS
# =========================================================================
@pytest.mark.asyncio
async def test_ticket_notification_invalid_uuid(async_session):
    """
    Test that invalid UUID format is handled gracefully.

    Verifies that the service raises appropriate error for malformed ticket IDs.
    """
    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock()):
        with pytest.raises(ValueError):
            await send_ticket_notifications("invalid-uuid", "Message", session=async_session)


@pytest.mark.asyncio
async def test_ticket_notification_empty_message(async_session):
    """
    Test that notifications can be sent with empty message.

    Verifies that empty messages are handled (though not recommended).
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="empty@test.com", name="Empty User")
    async_session.add(user)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Empty Message Test",
        status=TicketStatus.OPEN,
        created_by_user_id=user.id,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    with patch("app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)):
        await send_ticket_notifications(str(ticket_id), "", session=async_session)

    result = await async_session.execute(select(TicketNotification))
    notif = result.scalar_one()

    assert notif.message == ""
    assert notif.status == TicketNotificationStatus.SENT


# =========================================================================
#  CONTEXT AND EMAIL CONTENT TESTS
# =========================================================================
@pytest.mark.asyncio
async def test_ticket_notification_email_context(async_session):
    """
    Test that email is called with correct context parameters.

    Verifies that the email template receives proper ticket information.
    """
    ticket_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="context@test.com", name="Context User")
    async_session.add(user)
    await async_session.commit()

    ticket = Ticket(
        id=ticket_id,
        title="Context Test Ticket",
        status=TicketStatus.IN_PROGRESS,
        created_by_user_id=user.id,
        organization_id=org_id,
        project_id=project_id,
    )

    async_session.add(ticket)
    await async_session.commit()

    with patch(
        "app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)
    ) as mock_email:
        await send_ticket_notifications(str(ticket_id), "Test activity", session=async_session)

        # Verify email was called with correct parameters
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args.kwargs

        assert call_kwargs["template_name"] == "ticket_notification.html"
        assert call_kwargs["subject"] == f"Ticket Update: {ticket.title}"
        assert call_kwargs["recipient"] == user.email
        assert call_kwargs["context"]["ticket_title"] == ticket.title
        assert call_kwargs["context"]["message"] == "Test activity"
        assert call_kwargs["context"]["status"] == TicketStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_ticket_notification_different_statuses(async_session):
    """
    Test notifications for tickets with different statuses.

    Verifies that ticket status is correctly passed to email context.
    """
    org_id = uuid4()
    project_id = uuid4()
    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")

    async_session.add_all([org, project])
    await async_session.commit()

    user = User(id=uuid4(), email="status@test.com", name="Status User")
    async_session.add(user)
    await async_session.commit()

    # Only use valid statuses: OPEN, IN_PROGRESS, CLOSED (RESOLVED doesn't exist)
    statuses = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.CLOSED]

    for status in statuses:
        ticket_id = uuid4()
        ticket = Ticket(
            id=ticket_id,
            title=f"Ticket {status.value}",
            status=status,
            created_by_user_id=user.id,
            organization_id=org_id,
            project_id=project_id,
        )

        async_session.add(ticket)
        await async_session.commit()

        with patch(
            "app.api.core.dependencies.send_mail.send_email", new=AsyncMock(return_value=True)
        ) as mock_email:
            await send_ticket_notifications(
                str(ticket_id), f"Status: {status.value}", session=async_session
            )

            call_kwargs = mock_email.call_args.kwargs
            assert call_kwargs["context"]["status"] == status
