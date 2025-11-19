"""Unit tests for ticket invitation routes"""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.tickets.routes.invitation_routes import (
    router as invitation_router,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project import Project
from app.api.modules.v1.tickets.models.ticket import Ticket
from app.api.utils.password import hash_password
from app.api.utils.jwt import create_access_token


@pytest.fixture
def app(pg_async_session: AsyncSession):
    """FastAPI app with test DB dependency override."""
    app = FastAPI()
    app.include_router(invitation_router, prefix="/api/v1")

    async def override_get_db():
        yield pg_async_session

    from app.api.db.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.mark.asyncio
async def test_invite_ticket_participants_success(app, pg_async_session):
    """Test POST /tickets/{id}/invite endpoint with valid data."""
    session = pg_async_session

    # Create organization
    org = Organization(name="Test Org", industry="Tech")
    session.add(org)
    await session.flush()

    # Create role
    role = Role(
        name="admin",
        organization_id=org.id,
        description="Admin role",
        permissions={},
    )
    session.add(role)
    await session.flush()

    # Create user
    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="admin@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Admin User",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    # Create project
    project = Project(
        organization_id=org.id,
        name="Test Project",
        description="A test project",
        is_active=True,
    )
    session.add(project)
    await session.flush()

    # Create ticket
    ticket = Ticket(
        organization_id=org.id,
        project_id=project.id,
        title="Test Ticket",
        description="Test ticket for invitations",
        status="open",
        priority="medium",
        created_by=user.id,
    )
    session.add(ticket)
    await session.flush()
    await session.commit()

    # Create access token
    token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        role_id=str(role.id),
    )

    # Make request
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            f"/api/v1/tickets/{ticket.id}/invite",
            json={
                "emails": ["user1@company.com", "user2@company.com"],
                "expiry_hours": 48,
                "message": "Please join this ticket",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["total_sent"] == 2
    assert len(data["data"]["successful_invites"]) == 2
    assert len(data["data"]["failed_invites"]) == 0


@pytest.mark.asyncio
async def test_invite_ticket_participants_invalid_ticket(app, pg_async_session):
    """Test inviting participants with non-existent ticket ID."""
    session = pg_async_session

    # Create organization
    org = Organization(name="Test Org", industry="Tech")
    session.add(org)
    await session.flush()

    # Create role
    role = Role(
        name="admin",
        organization_id=org.id,
        description="Admin role",
        permissions={},
    )
    session.add(role)
    await session.flush()

    # Create user
    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="admin@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Admin User",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    await session.commit()

    # Create access token
    token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        role_id=str(role.id),
    )

    # Make request with non-existent ticket ID
    import uuid

    fake_ticket_id = uuid.uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            f"/api/v1/tickets/{fake_ticket_id}/invite",
            json={
                "emails": ["user1@company.com"],
                "expiry_hours": 48,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_list_ticket_invitations(app, pg_async_session):
    """Test GET /tickets/{id}/invitations endpoint."""
    session = pg_async_session

    # Create organization
    org = Organization(name="Test Org", industry="Tech")
    session.add(org)
    await session.flush()

    # Create role
    role = Role(
        name="admin",
        organization_id=org.id,
        description="Admin role",
        permissions={},
    )
    session.add(role)
    await session.flush()

    # Create user
    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="admin@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Admin User",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    # Create project
    project = Project(
        organization_id=org.id,
        name="Test Project",
        description="A test project",
        is_active=True,
    )
    session.add(project)
    await session.flush()

    # Create ticket
    ticket = Ticket(
        organization_id=org.id,
        project_id=project.id,
        title="Test Ticket",
        description="Test ticket for invitations",
        status="open",
        priority="medium",
        created_by=user.id,
    )
    session.add(ticket)
    await session.flush()
    await session.commit()

    # Create access token
    token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        role_id=str(role.id),
    )

    # First create invitations
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await client.post(
            f"/api/v1/tickets/{ticket.id}/invite",
            json={
                "emails": ["user1@company.com", "user2@company.com"],
                "expiry_hours": 48,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Now list invitations
        response = await client.get(
            f"/api/v1/tickets/{ticket.id}/invitations",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) == 2
