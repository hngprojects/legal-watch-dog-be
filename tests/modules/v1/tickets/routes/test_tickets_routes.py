import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.modules.v1.tickets.routes.ticket_routes import invite_users_to_ticket
from app.api.modules.v1.tickets.schemas.ticket_invitation_schema import (
    InvitedUserResponse,
    InviteUsersToTicketRequest,
    InviteUsersToTicketResponse,
)
from fastapi import status

from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_invite_users_to_ticket_success():
    """Test successfully inviting users to a ticket via the route"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com", "user2@example.com"])

    invited_user = InvitedUserResponse(
        user_id=str(user1_id),
        email="user1@example.com",
        name="User One",
        invited_at=datetime.now(timezone.utc),
    )

    service_result = InviteUsersToTicketResponse(
        invited=[invited_user],
        already_invited=["user2@example.com"],
        not_found=[],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.success_response") as mock_success,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(return_value=service_result)
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "1 user(s) invited successfully. 1 user(s) already invited",
            "data": service_result.model_dump(),
        }
        mock_success.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True
        assert "1 user(s) invited successfully" in response["message"]
        assert "1 user(s) already invited" in response["message"]
        assert response["data"]["invited"][0]["email"] == "user1@example.com"
        assert response["data"]["already_invited"][0] == "user2@example.com"

        mock_service.invite_users_to_ticket.assert_awaited_once_with(
            ticket_id=ticket_id,
            emails=payload.emails,
            current_user_id=current_user_id,
        )


@pytest.mark.asyncio
async def test_invite_users_to_ticket_all_invited():
    """Test inviting users where all are successfully invited"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com", "user2@example.com"])

    invited_users = [
        InvitedUserResponse(
            user_id=str(user1_id),
            email="user1@example.com",
            name="User One",
            invited_at=datetime.now(timezone.utc),
        ),
        InvitedUserResponse(
            user_id=str(user2_id),
            email="user2@example.com",
            name="User Two",
            invited_at=datetime.now(timezone.utc),
        ),
    ]

    service_result = InviteUsersToTicketResponse(
        invited=invited_users,
        already_invited=[],
        not_found=[],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.success_response") as mock_success,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(return_value=service_result)
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "2 user(s) invited successfully",
            "data": service_result.model_dump(),
        }
        mock_success.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True
        assert "2 user(s) invited successfully" in response["message"]
        assert len(response["data"]["invited"]) == 2
        assert len(response["data"]["already_invited"]) == 0
        assert len(response["data"]["not_found"]) == 0


@pytest.mark.asyncio
async def test_invite_users_to_ticket_with_not_found():
    """Test inviting users where some emails are not found"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com", "notfound@example.com"])

    invited_user = InvitedUserResponse(
        user_id=str(user1_id),
        email="user1@example.com",
        name="User One",
        invited_at=datetime.now(timezone.utc),
    )

    service_result = InviteUsersToTicketResponse(
        invited=[invited_user],
        already_invited=[],
        not_found=["notfound@example.com"],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.success_response") as mock_success,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(return_value=service_result)
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "1 user(s) invited successfully. 1 email(s) not found in organization",
            "data": service_result.model_dump(),
        }
        mock_success.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True
        assert "1 user(s) invited successfully" in response["message"]
        assert "1 email(s) not found in organization" in response["message"]
        assert len(response["data"]["invited"]) == 1
        assert len(response["data"]["not_found"]) == 1
        assert response["data"]["not_found"][0] == "notfound@example.com"


@pytest.mark.asyncio
async def test_invite_users_to_ticket_no_changes():
    """Test inviting users where no changes are made (all already invited)"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com"])

    service_result = InviteUsersToTicketResponse(
        invited=[],
        already_invited=["user1@example.com"],
        not_found=[],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.success_response") as mock_success,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(return_value=service_result)
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "1 user(s) already invited",
            "data": service_result.model_dump(),
        }
        mock_success.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True
        assert "1 user(s) already invited" in response["message"]


@pytest.mark.asyncio
async def test_invite_users_to_ticket_ticket_not_found():
    """Test inviting users to a non-existent ticket"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com"])

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.error_response") as mock_error,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(side_effect=ValueError("Ticket not found"))
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_400_BAD_REQUEST,
            "success": False,
            "message": "Ticket not found",
        }
        mock_error.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_400_BAD_REQUEST
        assert response["success"] is False
        assert response["message"] == "Ticket not found"


@pytest.mark.asyncio
async def test_invite_users_to_ticket_user_not_member():
    """Test inviting users when current user is not a member of organization"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com"])

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.error_response") as mock_error,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(
            side_effect=ValueError(
                "You must be a member of the organization to invite users to this ticket"
            )
        )
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_400_BAD_REQUEST,
            "success": False,
            "message": "You must be a member of the organization to invite users to this ticket",
        }
        mock_error.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_400_BAD_REQUEST
        assert response["success"] is False
        assert "You must be a member of the organization" in response["message"]


@pytest.mark.asyncio
async def test_invite_users_to_ticket_no_permission():
    """Test inviting users when current user lacks permission"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com"])

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.error_response") as mock_error,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(
            side_effect=ValueError(
                "You do not have permission to invite users to tickets in this organization"
            )
        )
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_400_BAD_REQUEST,
            "success": False,
            "message": "You do not have permission to invite users to tickets in this organization",
        }
        mock_error.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_400_BAD_REQUEST
        assert response["success"] is False
        assert "You do not have permission" in response["message"]


@pytest.mark.asyncio
async def test_invite_users_to_ticket_internal_error():
    """Test inviting users when an unexpected error occurs"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com"])

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.error_response") as mock_error,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "success": False,
            "error": "Internal Server Error",
            "message": "Failed to invite users to ticket. Please try again.",
        }
        mock_error.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response["success"] is False
        assert response["error"] == "Internal Server Error"
        assert "Failed to invite users to ticket" in response["message"]


@pytest.mark.asyncio
async def test_invite_users_to_ticket_mixed_results_message():
    """Test that the message correctly combines all result categories"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(
        emails=["user1@example.com", "user2@example.com", "notfound@example.com"]
    )

    invited_user = InvitedUserResponse(
        user_id=str(user1_id),
        email="user1@example.com",
        name="User One",
        invited_at=datetime.now(timezone.utc),
    )

    service_result = InviteUsersToTicketResponse(
        invited=[invited_user],
        already_invited=["user2@example.com"],
        not_found=["notfound@example.com"],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.success_response") as mock_success,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(return_value=service_result)
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "1 user(s) invited successfully. 1 user(s) already invited. "
            "1 email(s) not found in organization",
            "data": service_result.model_dump(),
        }
        mock_success.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True

        message = response["message"]
        assert "1 user(s) invited successfully" in message
        assert "1 user(s) already invited" in message
        assert "1 email(s) not found in organization" in message

        assert message.count(". ") == 2


@pytest.mark.asyncio
async def test_invite_users_to_ticket_empty_results():
    """Test with empty results (edge case) - modified to use valid payload"""
    ticket_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(
        id=current_user_id,
        email="current@example.com",
        name="Current User",
    )

    payload = InviteUsersToTicketRequest(emails=["user1@example.com"])

    service_result = InviteUsersToTicketResponse(
        invited=[],
        already_invited=[],
        not_found=[],
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.ticket_routes.TicketService"
        ) as mock_service_class,
        patch("app.api.modules.v1.tickets.routes.ticket_routes.success_response") as mock_success,
    ):
        mock_service = MagicMock()
        mock_service.invite_users_to_ticket = AsyncMock(return_value=service_result)
        mock_service_class.return_value = mock_service

        expected_response = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "No changes made",
            "data": service_result.model_dump(),
        }
        mock_success.return_value = expected_response

        response = await invite_users_to_ticket(
            ticket_id=ticket_id,
            payload=payload,
            current_user=current_user,
            db=db,
        )

        assert response["status_code"] == status.HTTP_200_OK
        assert response["success"] is True
        assert response["message"] == "No changes made"
