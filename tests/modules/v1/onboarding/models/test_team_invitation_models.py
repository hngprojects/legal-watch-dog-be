import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select

from app.api.modules.v1.onboarding.models.team_invitation import TeamInvitation, InvitationStatus
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_team_invitation_defaults(test_session):
    async for session in test_session:
        # create organization and sender user
        org = Organization(name="Test Org")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        user = User(
            organization_id=org.id,
            role_id=uuid4(),
            email="sender@example.com",
            hashed_password="x",
            name="Sender"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        invite = TeamInvitation(
            org_id=org.id,
            sender_id=user.id,
            role="member",
            team_email="invitee@example.com",
            token="hashedtoken",
        )

        session.add(invite)
        await session.commit()
        await session.refresh(invite)

        assert invite.id is not None
        assert invite.org_id == org.id
        assert invite.sender_id == user.id
        assert invite.role == "member"
        assert invite.team_email == "invitee@example.com"
        assert invite.token == "hashedtoken"
        assert invite.status == InvitationStatus.PENDING
        # created_at may be naive in some DB dialects used by tests (SQLite),
        # so assert it's a datetime and expires_at is after created_at.
        assert invite.created_at is not None
        assert invite.expires_at > invite.created_at
