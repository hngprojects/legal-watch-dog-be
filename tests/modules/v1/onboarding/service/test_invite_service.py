import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from app.api.modules.v1.onboarding.service.invite_service import create_and_send_invite, create_and_send_bulk_invites
from app.api.modules.v1.onboarding.models.team_invitation import TeamInvitation

@pytest.mark.asyncio
async def test_create_and_send_invite():
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_user = AsyncMock()
    mock_user.organization_id = 1
    mock_user.id = 1
    mock_user.organization = "TestOrg"
    mock_user.name = "TestUser"

    with patch("app.api.modules.v1.onboarding.service.invite_service.send_email", new_callable=AsyncMock) as mock_send_email:
        mock_send_email.return_value = True

        with patch("app.api.modules.v1.onboarding.service.invite_service.TeamInvitation") as mock_team_invite:
            mock_team_invite.return_value = AsyncMock()
            mock_team_invite.return_value.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

            token = await create_and_send_invite(
                db=mock_db,
                current_user=mock_user,
                role="member",
                team_email="brightjohn081132@gmail.com",
                invitee_name="Invitee"
            )

            assert token
            mock_send_email.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_and_send_bulk_invites():
    mock_db = AsyncMock()
    mock_user = AsyncMock()
    mock_user.organization_id = 1
    mock_user.id = 1
    mock_user.organization = "TestOrg"
    mock_user.name = "TestUser"

    invites = [
        {"role": "admin", "team_email": "user1@example.com", "invitee_name": "User One"},
        {"role": "member", "team_email": "user2@example.com"},
        {"role": "viewer", "team_email": "invalid-email"},
    ]

    with patch("app.api.modules.v1.onboarding.service.invite_service.create_and_send_invite") as mock_create_and_send_invite:
        mock_create_and_send_invite.side_effect = ["token1", "token2", Exception("Invalid email address")]

        results = await create_and_send_bulk_invites(mock_db, mock_user, invites)
        assert results["success"] == 2
        assert results["failure"] == 1