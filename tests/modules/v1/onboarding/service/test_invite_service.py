import pytest
from uuid import uuid4
from sqlalchemy import select

from app.api.modules.v1.onboarding.service import invite_service as invite_mod
from app.api.modules.v1.onboarding.models.team_invitation import TeamInvitation
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_create_and_send_invite_calls_send_email(monkeypatch, test_session):
    async for session in test_session:
        # setup org and user
        org = Organization(name="Service Org")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        user = User(
            organization_id=org.id,
            role_id=uuid4(),
            email="creator@example.com",
            hashed_password="x",
            name="Creator"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # capture send_email calls
        called = {}

        async def fake_send_email(template_name, subject, recipient, context):
            called['template'] = template_name
            called['subject'] = subject
            called['recipient'] = recipient
            called['context'] = context
            return True

        # patch the send_email used inside invite_service
        monkeypatch.setattr(invite_mod, 'send_email', fake_send_email)

        # Call the service using the DB-backed user as current_user
        token = await invite_mod.create_and_send_invite(
            session,
            current_user=user,
            role="member",
            team_email="invitee@example.com",
            invitee_name="Invitee"
        )

        assert token is not None
        # confirm DB row created
        stmt = select(TeamInvitation).where(TeamInvitation.team_email == "invitee@example.com")
        res = await session.exec(stmt)
        inv = res.scalars().first()
        assert inv is not None
        assert inv.team_email == "invitee@example.com"
        assert inv.org_id == org.id
        # stored token should not equal raw token
        assert inv.token != token

        # confirm send_email called with expected values
        assert called.get('template') == 'invite.html'
        assert called.get('recipient') == 'invitee@example.com'
        ctx = called.get('context')
        assert 'accept_url' in ctx
        assert 'org_name' in ctx
