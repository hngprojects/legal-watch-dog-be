import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.modules.v1.tickets.routes.participant_routes import invite_participants
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    InviteParticipantsRequest,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_invite_participants_ticket_not_found():
    """Test inviting participants to a non-existent ticket"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="admin@example.com",
        name="Admin User",
    )

    payload = InviteParticipantsRequest(
        emails=["test@example.com"],
    )

    db = AsyncMock()

    with (
        patch("app.api.modules.v1.tickets.routes.participant_routes.error_response") as mock_error,
    ):
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_ticket_result)

        expected_response = {
            "status_code": status.HTTP_404_NOT_FOUND,
            "success": False,
            "message": "Ticket not found",
        }
        mock_error.return_value = expected_response

        response = await invite_participants(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_404_NOT_FOUND
        assert response["success"] is False
        assert response["message"] == "Ticket not found"


@pytest.mark.asyncio
async def test_invite_participants_no_permission():
    """Test inviting participants without proper permissions"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="user@example.com",
        name="Regular User",
    )

    payload = InviteParticipantsRequest(
        emails=["test@example.com"],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.participant_routes.ParticipantService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.participant_routes.error_response") as mock_error,
        patch(
            "app.api.modules.v1.tickets.routes.participant_routes.require_billing_access"
        ) as mock_billing,
    ):
        mock_ticket = MagicMock()
        mock_ticket.organization_id = uuid.uuid4()
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalar_one_or_none.return_value = mock_ticket
        db.execute = AsyncMock(return_value=mock_ticket_result)

        mock_billing.return_value = AsyncMock()

        mock_service = MagicMock()
        mock_service.invite_participants = AsyncMock(
            side_effect=ValueError("You do not have permission to invite participants")
        )
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_400_BAD_REQUEST,
            "success": False,
            "message": "You do not have permission to invite participants",
        }
        mock_error.return_value = expected_response

        response = await invite_participants(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_400_BAD_REQUEST
        assert response["success"] is False
        assert "You do not have permission" in response["message"]
