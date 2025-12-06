import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketStatus
from app.api.modules.v1.tickets.service.participant_service import ParticipantService
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_invite_participants_ticket_not_found():
    """Test inviting participants to a non-existent ticket"""
    db = MagicMock()
    db.execute = AsyncMock()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = None
    db.execute.return_value = ticket_result

    service = ParticipantService(db)

    with pytest.raises(ValueError, match="Ticket not found"):
        await service.invite_participants(
            ticket_id=uuid.uuid4(),
            emails=["test@example.com"],
            current_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_invite_participants_no_permission():
    """Test inviting participants without proper permissions"""
    db = MagicMock()
    db.execute = AsyncMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
        status=TicketStatus.OPEN,
    )
    ticket.organization = Organization(id=org_id, name="Test Org")

    current_user = User(id=current_user_id, email="user@example.com")

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    db.execute.side_effect = [ticket_result, current_user_result]

    with (
        patch(
            "app.api.modules.v1.tickets.service.participant_service.TenantGuard"
        ) as mock_tenant_guard,
        patch(
            "app.api.modules.v1.tickets.service.participant_service.check_user_permission"
        ) as mock_check_permission,
    ):
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        mock_check_permission.return_value = False

        service = ParticipantService(db)

        with pytest.raises(ValueError, match="You do not have permission to invite participants"):
            await service.invite_participants(
                ticket_id=ticket_id,
                emails=["test@example.com"],
                current_user_id=current_user_id,
            )
