import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
)


@pytest.mark.asyncio
async def test_send_revision_notifications_creates_and_sends_email():
    """Test that send_revision_notifications creates a notification and sends an email
    when no prior notification exists for the user and revision.
    """
    revision_id = str(uuid.uuid4())

    mock_session = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session

    with (
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.AsyncSessionLocal",
            return_value=mock_ctx,
        ),
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.engine",
            new=MagicMock(dispose=AsyncMock()),
        ),
    ):
        mock_revision = MagicMock()
        mock_revision.id = revision_id
        mock_revision.source_id = uuid.uuid4()
        mock_revision.ai_summary = "AI summary text"

        mock_source = MagicMock()
        mock_source.jurisdiction_id = uuid.uuid4()

        mock_jurisdiction = MagicMock()
        mock_jurisdiction.project_id = uuid.uuid4()

        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.organization_id = uuid.uuid4()

        mock_project_user = MagicMock()
        mock_project_user.user_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.id = mock_project_user.user_id
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"

        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_revision),
            MagicMock(scalar_one_or_none=lambda: mock_source),
            MagicMock(scalar_one_or_none=lambda: mock_jurisdiction),
            MagicMock(scalar_one_or_none=lambda: mock_project),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [mock_project_user])),
            MagicMock(scalar_one_or_none=lambda: mock_user),
            MagicMock(scalar_one_or_none=lambda: None),
        ]

        with patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.send_email",
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.revision_notification_task import (
                send_revision_notifications,
            )

            await send_revision_notifications(revision_id)

            assert mock_send_email.await_count == 1

            mock_session.add.assert_called()
            mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_send_revision_notifications_skips_already_sent():
    """Test that send_revision_notifications skips sending email and creating"""
    revision_id = str(uuid.uuid4())

    mock_session = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session

    with (
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.AsyncSessionLocal",
            return_value=mock_ctx,
        ),
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.engine",
            new=MagicMock(dispose=AsyncMock()),
        ),
    ):
        mock_revision = MagicMock(source_id=uuid.uuid4())
        mock_source = MagicMock(jurisdiction_id=uuid.uuid4())
        mock_jurisdiction = MagicMock(project_id=uuid.uuid4())
        mock_project = MagicMock(id=uuid.uuid4())
        mock_project_user = MagicMock(user_id=uuid.uuid4())
        mock_user = MagicMock(id=mock_project_user.user_id, email="u@test.com")

        mock_existing_notification = Notification(
            revision_id=uuid.uuid4(),
            user_id=mock_user.id,
            message="Old msg",
            status=NotificationStatus.SENT,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_revision),
            MagicMock(scalar_one_or_none=lambda: mock_source),
            MagicMock(scalar_one_or_none=lambda: mock_jurisdiction),
            MagicMock(scalar_one_or_none=lambda: mock_project),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [mock_project_user])),
            MagicMock(scalar_one_or_none=lambda: mock_user),
            MagicMock(scalar_one_or_none=lambda: mock_existing_notification),
        ]

        with patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.send_email",
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.revision_notification_task import (
                send_revision_notifications,
            )

            await send_revision_notifications(revision_id)

            mock_send_email.assert_not_called()

            mock_session.add.assert_not_called()
            mock_session.commit.assert_not_awaited()
