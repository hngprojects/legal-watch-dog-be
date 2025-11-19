import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.api.modules.v1.onboarding.service.invite_service import (
    create_and_send_invite,
    create_and_send_bulk_invites,
)
from app.api.modules.v1.onboarding.models.team_invitation import TeamInvitation, InvitationStatus


def _mock_db_with_query_result(result):
    """Helper to mock SQLAlchemy scalar_one_or_none() results."""
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=result)

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.rollback = AsyncMock()
    add_mock = MagicMock()
    mock_db.add = add_mock

    return mock_db


@pytest.mark.asyncio
async def test_create_and_send_invite():
    # DB returns: no existing invite
    mock_db = _mock_db_with_query_result(None)

    mock_user = MagicMock()
    mock_user.organization_id = 1
    mock_user.id = 123
    mock_user.organization = "TestOrg"
    mock_user.name = "TestUser"

    with patch(
        "app.api.modules.v1.onboarding.service.invite_service.send_email",
        new_callable=AsyncMock
    ) as mock_send_email:

        mock_send_email.return_value = True

        # patch ONLY the constructor return value, NOT the class
        with patch.object(TeamInvitation, "__init__", return_value=None) as mock_init:
            # Patch attribute assignment
            invite_instance = TeamInvitation()
            invite_instance.id = "abc-123"
            invite_instance.token = "abc-123"
            invite_instance.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

            with patch(
                "app.api.modules.v1.onboarding.service.invite_service.TeamInvitation",
                return_value=invite_instance
            ):

                token = await create_and_send_invite(
                    db=mock_db,
                    current_user=mock_user,
                    role="member",
                    team_email="john@example.com",
                    invitee_name="John Doe",
                )

                assert token == "abc-123"
                mock_send_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_and_send_invite_duplicate():
    existing_invite = TeamInvitation(
        org_id=1,
        sender_id=1,
        role="member",
        team_email="john@example.com",
        token="abc",
        status=InvitationStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )

    mock_db = _mock_db_with_query_result(existing_invite)

    mock_user = MagicMock()
    mock_user.organization_id = 1
    mock_user.id = 1

    result = await create_and_send_invite(
        db=mock_db,
        current_user=mock_user,
        role="member",
        team_email="john@example.com",
        invitee_name="John Doe",
    )

    assert result is None  # no new token created


@pytest.mark.asyncio
async def test_create_and_send_bulk_invites():
    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.organization_id = 1
    mock_user.id = 1
    mock_user.organization = "TestOrg"
    mock_user.name = "TestUser"

    invites = [
        {"role": "admin", "team_email": "user1@example.com", "invitee_name": "User One"},
        {"role": "member", "team_email": "user2@example.com"},
        {"role": "viewer", "team_email": "invalid-email"},
    ]

    with patch(
        "app.api.modules.v1.onboarding.service.invite_service.create_and_send_invite",
        side_effect=["token1", "token2", Exception("Invalid email")]
    ):

        results = await create_and_send_bulk_invites(mock_db, mock_user, invites)

        assert results["success"] == 2
        assert results["failure"] == 1
