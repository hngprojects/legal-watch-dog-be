"""Unit tests for ticket invitation service functions"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
import uuid

from app.api.modules.v1.tickets.service.invitation_service import (
    get_ticket_with_access_check,
    create_invitation,
    invite_participants,
    revoke_invitation,
    accept_invitation,
    get_ticket_invitations,
)
from app.api.modules.v1.tickets.models.ticket import Ticket
from app.api.modules.v1.tickets.models.invitation_model import TicketInvitation
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.tickets.schemas.invitation import InviteParticipantRequest
from fastapi import HTTPException, BackgroundTasks


@pytest.fixture
def mock_user():
    """Create a mock user"""
    return User(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        email="test@company.com",
        name="Test User",
        hashed_password="hashed",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture
def mock_ticket(mock_user):
    """Create a mock ticket"""
    return Ticket(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        project_id=uuid.uuid4(),
        created_by=mock_user.id,
        title="Test Ticket",
        description="Test description",
        status="open",
        priority="medium",
    )


@pytest.fixture
def mock_invitation(mock_ticket, mock_user):
    """Create a mock invitation"""
    return TicketInvitation(
        id=uuid.uuid4(),
        ticket_id=mock_ticket.id,
        invited_by=mock_user.id,
        invitee_email="invitee@company.com",
        token="test-token-123",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        is_accepted=False,
        is_revoked=False,
    )


@pytest.mark.asyncio
async def test_get_ticket_with_access_check_success(mock_user, mock_ticket):
    """Test successful ticket access check"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_ticket

    result = await get_ticket_with_access_check(
        db=mock_db,
        ticket_id=mock_ticket.id,
        user=mock_user,
    )

    assert result == mock_ticket
    mock_db.scalar.assert_called_once()


@pytest.mark.asyncio
async def test_get_ticket_with_access_check_not_found(mock_user):
    """Test ticket access check when ticket not found"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_ticket_with_access_check(
            db=mock_db,
            ticket_id=uuid.uuid4(),
            user=mock_user,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_invitation_new(mock_ticket, mock_user):
    """Test creating a new invitation"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None  # No existing invitation
    mock_db.add = Mock()  # Non-async method

    result = await create_invitation(
        db=mock_db,
        ticket=mock_ticket,
        invitee_email="newuser@company.com",
        invited_by=mock_user,
        expiry_hours=48,
    )

    assert result.ticket_id == mock_ticket.id
    assert result.invited_by == mock_user.id
    assert result.invitee_email == "newuser@company.com"
    assert result.token is not None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_invitation_update_existing(
    mock_ticket, mock_user, mock_invitation
):
    """Test updating an existing active invitation"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_invitation
    mock_db.add = Mock()  # Non-async method
    old_token = mock_invitation.token

    result = await create_invitation(
        db=mock_db,
        ticket=mock_ticket,
        invitee_email=mock_invitation.invitee_email,
        invited_by=mock_user,
        expiry_hours=24,
    )

    assert result.invitee_email == mock_invitation.invitee_email
    assert result.token != old_token  # Token should be regenerated
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.modules.v1.tickets.service.invitation_service.send_invitation_email")
async def test_send_invitation_email(
    mock_send_email, mock_invitation, mock_ticket, mock_user
):
    """Test sending invitation email"""
    mock_send_email.return_value = True

    from app.api.modules.v1.tickets.service.invitation_service import (
        send_invitation_email,
    )

    result = await send_invitation_email(
        invitation=mock_invitation,
        ticket=mock_ticket,
        invited_by=mock_user,
        custom_message="Please join this ticket",
    )

    assert result is True


@pytest.mark.asyncio
@patch(
    "app.api.modules.v1.tickets.service.invitation_service.get_ticket_with_access_check"
)
@patch("app.api.modules.v1.tickets.service.invitation_service.create_invitation")
async def test_invite_participants_success(
    mock_create_inv, mock_get_ticket, mock_ticket, mock_user, mock_invitation
):
    """Test inviting multiple participants successfully"""
    mock_get_ticket.return_value = mock_ticket
    mock_create_inv.return_value = mock_invitation

    mock_db = AsyncMock()
    background_tasks = BackgroundTasks()

    data = InviteParticipantRequest(
        emails=["user1@company.com", "user2@company.com"],
        expiry_hours=48,
    )

    successful, failed = await invite_participants(
        db=mock_db,
        ticket_id=mock_ticket.id,
        data=data,
        current_user=mock_user,
        background_tasks=background_tasks,
    )

    assert len(successful) == 2
    assert len(failed) == 0
    assert mock_create_inv.call_count == 2


@pytest.mark.asyncio
async def test_revoke_invitation_success(mock_user, mock_invitation):
    """Test revoking an invitation"""
    mock_db = AsyncMock()
    mock_db.scalar.side_effect = [mock_invitation, Mock()]  # invitation, then ticket
    mock_db.add = Mock()  # Non-async method

    mock_path = (
        "app.api.modules.v1.tickets.service.invitation_service."
        "get_ticket_with_access_check"
    )
    with patch(mock_path) as mock_get_ticket:
        mock_get_ticket.return_value = Mock()

        result = await revoke_invitation(
            db=mock_db,
            invitation_id=mock_invitation.id,
            current_user=mock_user,
        )

        assert result.is_revoked is True
        assert result.revoked_by == mock_user.id
        assert result.revoked_at is not None
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_revoke_invitation_not_found(mock_user):
    """Test revoking a non-existent invitation"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await revoke_invitation(
            db=mock_db,
            invitation_id=uuid.uuid4(),
            current_user=mock_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_revoke_invitation_already_revoked(mock_user, mock_invitation):
    """Test revoking an already revoked invitation"""
    mock_invitation.is_revoked = True
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_invitation

    with pytest.raises(HTTPException) as exc_info:
        await revoke_invitation(
            db=mock_db,
            invitation_id=mock_invitation.id,
            current_user=mock_user,
        )

    assert exc_info.value.status_code == 400
    assert "already revoked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_accept_invitation_success(mock_invitation):
    """Test accepting a valid invitation"""
    # Create user with matching email
    user = User(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        email=mock_invitation.invitee_email,
        name="Invitee User",
        hashed_password="hashed",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )

    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_invitation
    mock_db.add = Mock()  # Non-async method

    result = await accept_invitation(
        db=mock_db,
        token=mock_invitation.token,
        current_user=user,
    )

    assert result.is_accepted is True
    assert result.accepted_at is not None
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_accept_invitation_invalid_token(mock_user):
    """Test accepting invitation with invalid token"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await accept_invitation(
            db=mock_db,
            token="invalid-token",
            current_user=mock_user,
        )

    assert exc_info.value.status_code == 404
    assert "invalid" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_accept_invitation_wrong_email(mock_invitation, mock_user):
    """Test accepting invitation with wrong email"""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_invitation

    with pytest.raises(HTTPException) as exc_info:
        await accept_invitation(
            db=mock_db,
            token=mock_invitation.token,
            current_user=mock_user,  # Different email from invitation
        )

    assert exc_info.value.status_code == 403
    assert "different email" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_accept_invitation_expired(mock_invitation, mock_user):
    """Test accepting an expired invitation"""
    mock_invitation.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    mock_invitation.invitee_email = mock_user.email

    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_invitation

    with pytest.raises(HTTPException) as exc_info:
        await accept_invitation(
            db=mock_db,
            token=mock_invitation.token,
            current_user=mock_user,
        )

    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
@patch(
    "app.api.modules.v1.tickets.service.invitation_service.get_ticket_with_access_check"
)
async def test_get_ticket_invitations(mock_get_ticket, mock_ticket, mock_user):
    """Test retrieving all invitations for a ticket"""
    mock_get_ticket.return_value = mock_ticket

    invitations = [
        TicketInvitation(
            id=uuid.uuid4(),
            ticket_id=mock_ticket.id,
            invited_by=mock_user.id,
            invitee_email=f"user{i}@company.com",
            token=f"token-{i}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        for i in range(3)
    ]

    # Create proper mock for db.exec() which returns result with .all()
    mock_result = Mock()
    mock_result.all.return_value = invitations

    mock_db = AsyncMock()
    mock_db.exec.return_value = mock_result

    result = await get_ticket_invitations(
        db=mock_db,
        ticket_id=mock_ticket.id,
        current_user=mock_user,
    )

    assert len(result) == 3
    mock_get_ticket.assert_called_once()
