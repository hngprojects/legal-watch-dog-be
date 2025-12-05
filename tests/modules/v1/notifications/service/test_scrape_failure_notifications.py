from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.api.modules.v1.notifications.models.revision_notification import (
    NotificationStatus,
    NotificationType,
)
from app.api.modules.v1.notifications.service.scrape_failure_notification_task import (
    send_scrape_failure_notifications,
)


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_ids():
    """Generate sample UUIDs for testing."""
    return {
        "source_id": str(uuid4()),
        "job_id": str(uuid4()),
        "user_id": str(uuid4()),
        "project_id": str(uuid4()),
        "jurisdiction_id": str(uuid4()),
        "organization_id": str(uuid4()),
    }


@pytest.fixture
def mock_objects(sample_ids):
    """Create mock database objects for testing."""
    # Mock Project
    project = MagicMock()
    project.id = UUID(sample_ids["project_id"])
    project.name = "Test Project"
    project.organization_id = UUID(sample_ids["organization_id"])

    # Mock Jurisdiction
    jurisdiction = MagicMock()
    jurisdiction.id = UUID(sample_ids["jurisdiction_id"])
    jurisdiction.name = "Test Jurisdiction"
    jurisdiction.project = project  # link project

    # Mock Source
    source = MagicMock()
    source.id = UUID(sample_ids["source_id"])
    source.name = "Test Source"
    source.jurisdiction = jurisdiction  # link jurisdiction

    # Mock ScrapeJob
    job = MagicMock()
    job.id = UUID(sample_ids["job_id"])
    job.completed_at = datetime.now(timezone.utc)

    # Mock ProjectUser
    project_user = MagicMock()
    project_user.user_id = UUID(sample_ids["user_id"])

    # Mock User
    user = MagicMock()
    user.id = UUID(sample_ids["user_id"])
    user.email = "test@example.com"
    user.name = "Test User"

    return {
        "source": source,
        "job": job,
        "jurisdiction": jurisdiction,
        "project": project,
        "project_user": project_user,
        "user": user,
    }


class TestScrapeFailureNotifications:
    """Test class for scrape failure notification functionality."""

    @pytest.mark.asyncio
    @patch(
        "app.api.modules.v1.notifications.service.scrape_failure_notification_task.AsyncSessionLocal"
    )
    @patch("app.api.modules.v1.notifications.service.scrape_failure_notification_task.send_email")
    async def test_send_scrape_failure_notifications_success(
        self,
        mock_send_email,
        mock_session_local,
        mock_session,
        sample_ids,
        mock_objects,
    ):
        """Test successful sending of scrape failure notifications."""
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_send_email.return_value = True

        # Mock execute results in order of queries
        mock_session.execute.side_effect = [
            # Source (with jurisdiction & project loaded)
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["source"])),
            # ScrapeJob
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["job"])),
            # ProjectUser list
            MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        all=MagicMock(return_value=[mock_objects["project_user"]])
                    )
                )
            ),
            # User
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["user"])),
            # Existing Notification check
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]

        result = await send_scrape_failure_notifications(
            source_id=sample_ids["source_id"],
            job_id=sample_ids["job_id"],
            error_message="Connection timeout",
        )

        assert isinstance(result, dict)
        assert result["sent"] == 1
        assert result["failed"] == 0
        assert result["source_id"] == sample_ids["source_id"]

        mock_send_email.assert_called_once()
        assert mock_session.add.called
        notification_arg = mock_session.add.call_args[0][0]
        assert notification_arg.notification_type == NotificationType.SCRAPE_FAILED
        assert notification_arg.status == NotificationStatus.SENT
        assert notification_arg.scrape_job_id == UUID(sample_ids["job_id"])
        assert mock_session.commit.call_count >= 2

    @pytest.mark.asyncio
    @patch(
        "app.api.modules.v1.notifications.service.scrape_failure_notification_task.AsyncSessionLocal"
    )
    async def test_send_scrape_failure_notifications_idempotency(
        self, mock_session_local, mock_session, sample_ids, mock_objects
    ):
        """Test idempotency - duplicate notifications are not sent."""
        mock_session_local.return_value.__aenter__.return_value = mock_session

        existing_notification = MagicMock()
        existing_notification.notification_id = uuid4()
        existing_notification.status = NotificationStatus.SENT

        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["source"])),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["job"])),
            MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        all=MagicMock(return_value=[mock_objects["project_user"]])
                    )
                )
            ),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["user"])),
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing_notification)),
        ]

        result = await send_scrape_failure_notifications(
            source_id=sample_ids["source_id"],
            job_id=sample_ids["job_id"],
            error_message="Connection timeout",
        )

        assert result["skipped"] == 1
        assert result["sent"] == 0
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "app.api.modules.v1.notifications.service.scrape_failure_notification_task.AsyncSessionLocal"
    )
    async def test_send_scrape_failure_notifications_no_source(
        self, mock_session_local, mock_session, sample_ids
    ):
        """Test handling when source is not found."""
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        )

        result = await send_scrape_failure_notifications(
            source_id=sample_ids["source_id"],
            job_id=sample_ids["job_id"],
            error_message="Connection timeout",
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Source not found" in result["error"]

    @pytest.mark.asyncio
    @patch(
        "app.api.modules.v1.notifications.service.scrape_failure_notification_task.AsyncSessionLocal"
    )
    @patch("app.api.modules.v1.notifications.service.scrape_failure_notification_task.send_email")
    async def test_send_scrape_failure_notifications_email_failure(
        self,
        mock_send_email,
        mock_session_local,
        mock_session,
        sample_ids,
        mock_objects,
    ):
        """Test handling when email sending fails."""
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_send_email.return_value = False

        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["source"])),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["job"])),
            MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        all=MagicMock(return_value=[mock_objects["project_user"]])
                    )
                )
            ),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_objects["user"])),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]

        result = await send_scrape_failure_notifications(
            source_id=sample_ids["source_id"],
            job_id=sample_ids["job_id"],
            error_message="Connection timeout",
        )

        assert result["failed"] == 1
        assert result["sent"] == 0


def test_notification_type_enum():
    """Test that NotificationType enum includes SCRAPE_FAILED."""
    assert hasattr(NotificationType, "SCRAPE_FAILED")
    assert NotificationType.SCRAPE_FAILED.value == "SCRAPE_FAILED"


def test_notification_status_enum():
    """Test that NotificationStatus enum has required values."""
    required_statuses = ["PENDING", "SENT", "FAILED", "READ"]
    for status in required_statuses:
        assert hasattr(NotificationStatus, status)
