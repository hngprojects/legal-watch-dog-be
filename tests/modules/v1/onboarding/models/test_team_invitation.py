import pytest
from datetime import timedelta, timezone
from uuid import uuid4

from app.api.modules.v1.onboarding.models.team_invitation import (
    TeamInvitation,
    InvitationStatus,
)


def test_team_invitation_defaults_and_fields():
    """Verify default values and basic field behavior of TeamInvitation."""
    org_id = uuid4()
    sender_id = uuid4()

    invite = TeamInvitation(
        org_id=org_id,
        sender_id=sender_id,
        role="member",
        team_email="alice@example.com",
        token="sometoken",
    )

    # required fields are set
    assert invite.org_id == org_id
    assert invite.sender_id == sender_id
    assert invite.team_email == "alice@example.com"
    assert invite.token == "sometoken"

    # status default
    assert invite.status == InvitationStatus.PENDING

    # created_at is timezone-aware (UTC)
    assert invite.created_at.tzinfo is not None
    assert invite.created_at.tzinfo.utcoffset(invite.created_at) is not None

    # expires_at is roughly 7 days after created_at
    delta = invite.expires_at - invite.created_at
    assert abs(delta - timedelta(days=7)) < timedelta(seconds=5)

    # accepted_at defaults to None
    assert invite.accepted_at is None


def test_invitation_status_enum_values():
    assert InvitationStatus.PENDING.value == "pending"
    assert InvitationStatus.ACCEPTED.value == "accepted"
    assert InvitationStatus.EXPIRED.value == "expired"
    assert InvitationStatus.REVOKED.value == "revoked"
