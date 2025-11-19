import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.tickets.routes.ticket_routes import router as ticket_router
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project import Project
from app.api.utils.password import hash_password
from app.api.utils.jwt import create_access_token


@pytest.fixture
def app(pg_async_session: AsyncSession):
    """FastAPI app with test DB dependency override."""
    app = FastAPI()
    app.include_router(ticket_router, prefix="/api/v1")

    async def override_get_db():
        yield pg_async_session

    from app.api.db.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.mark.asyncio
async def test_create_ticket_route_success(app, pg_async_session):
    """Test POST /tickets endpoint with valid data."""
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
        email="test@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Test User",
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
            "/api/v1/tickets",
            json={
                "title": "Test Ticket",
                "description": "This is a test ticket",
                "project_id": str(project.id),
                "priority": "high",
                "status": "open",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["status_code"] == 201
    assert data["message"] == "Ticket created successfully"
    assert data["data"]["title"] == "Test Ticket"
    assert data["data"]["description"] == "This is a test ticket"
    assert data["data"]["project_id"] == str(project.id)
    assert data["data"]["organization_id"] == str(org.id)
    assert data["data"]["created_by"] == str(user.id)
    assert data["data"]["priority"] == "high"
    assert data["data"]["status"] == "open"
    assert data["data"]["assigned_to"] is None


@pytest.mark.asyncio
async def test_create_ticket_route_with_assignment(app, pg_async_session):
    """Test POST /tickets endpoint with assigned user."""
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

    # Create creator user
    creator = User(
        organization_id=org.id,
        role_id=role.id,
        email="creator@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Creator User",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )
    session.add(creator)
    await session.flush()

    # Create assignee user
    assignee = User(
        organization_id=org.id,
        role_id=role.id,
        email="assignee@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Assignee User",
        auth_provider="local",
        is_active=True,
        is_verified=True,
    )
    session.add(assignee)
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
    await session.commit()

    # Create access token
    token = create_access_token(
        user_id=str(creator.id),
        organization_id=str(org.id),
        role_id=str(role.id),
    )

    # Make request
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Assigned Ticket",
                "description": "This ticket is assigned",
                "project_id": str(project.id),
                "assigned_to": str(assignee.id),
                "priority": "medium",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["assigned_to"] == str(assignee.id)
    assert data["data"]["created_by"] == str(creator.id)


@pytest.mark.asyncio
async def test_create_ticket_route_unauthorized(app):
    """Test POST /tickets endpoint without authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Unauthorized Ticket",
                "description": "Should fail",
                "project_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_ticket_route_invalid_project(app, pg_async_session):
    """Test POST /tickets endpoint with invalid project ID."""
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
        email="test@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Test User",
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

    # Make request with invalid project ID
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Invalid Project Ticket",
                "description": "Should fail",
                "project_id": "invalid-uuid",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_ticket_route_missing_title(app, pg_async_session):
    """Test POST /tickets endpoint without title field."""
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
        email="test@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Test User",
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
    await session.commit()

    # Create access token
    token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        role_id=str(role.id),
    )

    # Make request without title
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/tickets",
            json={
                "description": "Missing title",
                "project_id": str(project.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_ticket_route_default_values(app, pg_async_session):
    """Test POST /tickets endpoint uses default values for priority and status."""
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
        email="test@company.com",
        hashed_password=hash_password("Test@1234"),
        name="Test User",
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
    await session.commit()

    # Create access token
    token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        role_id=str(role.id),
    )

    # Make request without priority and status
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/tickets",
            json={
                "title": "Default Values Ticket",
                "description": "Testing defaults",
                "project_id": str(project.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["priority"] == "medium"  # Default value
    assert data["data"]["status"] == "open"  # Default value
