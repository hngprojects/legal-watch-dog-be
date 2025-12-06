"""
Unit tests for manual ticket creation with mocked dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.tickets.models.ticket_model import TicketPriority, TicketStatus
from app.api.modules.v1.tickets.schemas.ticket_schema import TicketCreate
from app.api.modules.v1.tickets.service.ticket_service import TicketService


@pytest.mark.asyncio
async def test_create_manual_ticket_success():
    """Test successful manual ticket creation."""
    mock_db = AsyncMock()
    org_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    source_id = uuid4()
    revision_id = uuid4()
    jurisdiction_id = uuid4()

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.project_id = project_id
    mock_source.organization_id = org_id
    mock_source.jurisdiction_id = jurisdiction_id
    mock_source.name = "Test Source"
    mock_source.url = "https://test.com"

    mock_revision = MagicMock()
    mock_revision.id = revision_id
    mock_revision.source_id = source_id
    mock_revision.ai_summary = "Test summary"
    mock_revision.content_hash = "abc123"
    mock_revision.scraped_at = MagicMock()
    mock_revision.scraped_at.isoformat.return_value = "2025-12-06T10:00:00"
    mock_revision.ai_confidence_score = 0.8
    mock_revision.change_diffs = []

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.name = "Test Jurisdiction"

    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = mock_source

    revision_result = MagicMock()
    revision_result.scalar_one_or_none.return_value = mock_revision

    jurisdiction_result = MagicMock()
    jurisdiction_result.scalar_one_or_none.return_value = mock_jurisdiction

    mock_db.execute = AsyncMock(side_effect=[source_result, revision_result, jurisdiction_result])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.get_project_by_id",
            return_value=mock_project,
        ),
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_project_user_exists",
            return_value=True,
        ),
    ):
        ticket_data = TicketCreate(
            source_id=source_id,
            revision_id=revision_id,
            priority=TicketPriority.HIGH,
        )

        service = TicketService(db=mock_db)
        ticket = await service.create_manual_ticket(
            data=ticket_data, organization_id=org_id, user_id=user_id, project_id=project_id
        )

        assert ticket.title == "[Test Jurisdiction] Test Source - Change Detected"
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.status == TicketStatus.OPEN
        assert ticket.is_manual is True
        assert ticket.organization_id == org_id
        assert ticket.created_by_user_id == user_id
        assert ticket.source_id == source_id
        assert ticket.data_revision_id == revision_id
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_manual_ticket_project_not_found():
    """Test ticket creation when project doesn't exist."""
    mock_db = AsyncMock()
    org_id = uuid4()
    user_id = uuid4()
    source_id = uuid4()
    revision_id = uuid4()
    project_id = uuid4()

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.project_id = project_id

    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = mock_source
    mock_db.execute = AsyncMock(return_value=source_result)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.get_project_by_id",
        return_value=None,
    ):
        ticket_data = TicketCreate(
            source_id=source_id,
            revision_id=revision_id,
            priority=TicketPriority.MEDIUM,
        )

        service = TicketService(db=mock_db)

        with pytest.raises(ValueError, match="Project not found"):
            await service.create_manual_ticket(
                data=ticket_data, organization_id=org_id, user_id=user_id, project_id=project_id
            )


@pytest.mark.asyncio
async def test_create_manual_ticket_user_not_member():
    """Test ticket creation fails when user is not a project member."""
    mock_db = AsyncMock()
    org_id = uuid4()
    user_id = uuid4()
    source_id = uuid4()
    revision_id = uuid4()
    project_id = uuid4()

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.project_id = project_id

    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = mock_source
    mock_db.execute = AsyncMock(return_value=source_result)

    with (
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.get_project_by_id",
            return_value=mock_project,
        ),
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_project_user_exists",
            return_value=False,
        ),
    ):
        ticket_data = TicketCreate(
            source_id=source_id,
            revision_id=revision_id,
            priority=TicketPriority.LOW,
        )

        service = TicketService(db=mock_db)

        with pytest.raises(ValueError, match="must be a member of the project"):
            await service.create_manual_ticket(
                data=ticket_data, organization_id=org_id, user_id=user_id, project_id=project_id
            )
