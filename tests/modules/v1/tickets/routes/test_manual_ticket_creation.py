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

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

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
            title="Test Ticket",
            description="Test description",
            content={"type": "test"},
            priority=TicketPriority.HIGH,
            project_id=project_id,
        )

        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = TicketService(db=mock_db)
        ticket = await service.create_manual_ticket(
            data=ticket_data, organization_id=org_id, user_id=user_id
        )

        assert ticket.title == "Test Ticket"
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.status == TicketStatus.OPEN
        assert ticket.is_manual is True
        assert ticket.organization_id == org_id
        assert ticket.created_by_user_id == user_id
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_manual_ticket_project_not_found():
    """Test ticket creation when project doesn't exist."""
    mock_db = AsyncMock()
    org_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.get_project_by_id",
        return_value=None,
    ):
        ticket_data = TicketCreate(
            title="Test Ticket",
            priority=TicketPriority.MEDIUM,
            project_id=project_id,
        )

        service = TicketService(db=mock_db)

        with pytest.raises(ValueError, match="Project not found"):
            await service.create_manual_ticket(
                data=ticket_data, organization_id=org_id, user_id=user_id
            )


@pytest.mark.asyncio
async def test_create_manual_ticket_user_not_member():
    """Test ticket creation fails when user is not a project member."""
    mock_db = AsyncMock()
    org_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

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
            title="Test Ticket",
            priority=TicketPriority.LOW,
            project_id=project_id,
        )

        service = TicketService(db=mock_db)

        with pytest.raises(ValueError, match="must be a member of the project"):
            await service.create_manual_ticket(
                data=ticket_data, organization_id=org_id, user_id=user_id
            )
