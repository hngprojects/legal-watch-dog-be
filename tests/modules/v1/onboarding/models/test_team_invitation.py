import pytest
from datetime import datetime, timedelta, timezone
from app.api.modules.v1.onboarding.models.team_invitation import (
    TeamInvitation,
    InvitationStatus,
)


def test_team_invitation_defaults():
    invitation = TeamInvitation(
        org_id=1,
        sender_id=1,
        role="member",
        team_email="invitee@example.com",
        token="hashed_token",
    )

    assert invitation.status == InvitationStatus.PENDING
    assert invitation.expires_at >= datetime.now(timezone.utc)
    assert invitation.accepted_at is None


def test_team_invitation_expired():
    expired_invitation = TeamInvitation(
        org_id=1,
        sender_id=1,
        role="member",
        team_email="invitee@example.com",
        token="hashed_token",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    assert expired_invitation.expires_at < datetime.now(timezone.utc)


def test_team_invitation_relationships():
    invitation = TeamInvitation(
        org_id=1,
        sender_id=1,
        role="member",
        team_email="invitee@example.com",
        token="hashed_token",
    )

    # assert invitation.organization is None
    # assert invitation.sender is None
