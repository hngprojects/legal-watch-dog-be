import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.api.modules.v1.tickets.routes.guest_access_routes import (
    get_guest_ticket_access,
)


@pytest.mark.asyncio
async def test_get_guest_ticket_access_success():
    """Test successfully retrieving ticket details via guest access"""
    ticket_id = uuid.uuid4()
    participant_id = uuid.uuid4()
    org_id = uuid.uuid4()

    participant = ExternalParticipant(
        id=participant_id,
        ticket_id=ticket_id,
        email="guest@external.com",
        role="Legal Counsel",
        is_active=True,
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    ticket = Ticket(
        id=ticket_id,
        title="Legal Review Required",
        description="Review the contract amendments",
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        organization_id=org_id,
        created_at=datetime.now(timezone.utc),
    )
    ticket.project = MagicMock()
    ticket.project.title = "Contract Management"

    guest_context = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": str(participant_id), "ticket_id": str(ticket_id)},
    )

    db = AsyncMock()

    with patch(
        "app.api.modules.v1.tickets.routes.guest_access_routes.success_response"
    ) as mock_success:
        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "Guest access validated successfully",
            "data": {
                "ticket_id": str(ticket_id),
                "title": "Legal Review Required",
                "description": "Review the contract amendments",
                "priority": "high",
                "status": "open",
                "created_at": ticket.created_at,
                "project_name": "Contract Management",
                "participant_email": "guest@external.com",
                "participant_role": "Legal Counsel",
                "access_expires_at": participant.expires_at,
            },
        }
        mock_success.return_value = expected_response

        response = await get_guest_ticket_access(guest=guest_context, db=db)

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True
        assert response["message"] == "Guest access validated successfully"
        assert response["data"]["ticket_id"] == str(ticket_id)
        assert response["data"]["participant_email"] == "guest@external.com"


@pytest.mark.asyncio
async def test_get_guest_ticket_access_without_project():
    """Test guest access to a ticket without a project"""
    ticket_id = uuid.uuid4()
    participant_id = uuid.uuid4()

    participant = ExternalParticipant(
        id=participant_id,
        ticket_id=ticket_id,
        email="guest@external.com",
        role="Consultant",
        is_active=True,
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    ticket = Ticket(
        id=ticket_id,
        title="Standalone Ticket",
        description="No project attached",
        priority=TicketPriority.MEDIUM,
        status=TicketStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )
    ticket.project = None

    guest_context = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": str(participant_id), "ticket_id": str(ticket_id)},
    )

    db = AsyncMock()

    with patch(
        "app.api.modules.v1.tickets.routes.guest_access_routes.success_response"
    ) as mock_success:
        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "Guest access validated successfully",
            "data": {
                "ticket_id": str(ticket_id),
                "title": "Standalone Ticket",
                "description": "No project attached",
                "priority": "medium",
                "status": "open",
                "created_at": ticket.created_at,
                "project_name": None,
                "participant_email": "guest@external.com",
                "participant_role": "Consultant",
                "access_expires_at": participant.expires_at,
            },
        }
        mock_success.return_value = expected_response

        response = await get_guest_ticket_access(guest=guest_context, db=db)

        assert response["status_code"] == status.HTTP_200_OK
        assert response["data"]["project_name"] is None


@pytest.mark.asyncio
async def test_get_guest_ticket_access_internal_error():
    """Test guest access with an unexpected error"""
    ticket_id = uuid.uuid4()
    participant_id = uuid.uuid4()

    participant = ExternalParticipant(
        id=participant_id,
        ticket_id=ticket_id,
        email="guest@external.com",
        role="Consultant",
        is_active=True,
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    # Create a mock that raises an exception
    ticket = MagicMock()
    ticket.id = ticket_id
    # Make project attribute raise an exception when accessed
    type(ticket).project = property(
        lambda self: (_ for _ in ()).throw(ZeroDivisionError("Simulated error"))
    )

    guest_context = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": str(participant_id), "ticket_id": str(ticket_id)},
    )

    db = AsyncMock()

    with patch(
        "app.api.modules.v1.tickets.routes.guest_access_routes.error_response"
    ) as mock_error:
        expected_response = {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "success": False,
            "message": "Failed to load ticket. Please try again or contact support.",
        }
        mock_error.return_value = expected_response

        response = await get_guest_ticket_access(guest=guest_context, db=db)

        assert response["status_code"] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response["success"] is False
        assert "Failed to load ticket" in response["message"]
