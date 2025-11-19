import pytest
import uuid
from fastapi import HTTPException
from app.api.modules.v1.tickets.service.ticket_service import (
    create_ticket,
    get_ticket_by_id,
)
from app.api.modules.v1.tickets.schemas.ticket import TicketCreateRequest
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project import Project
from app.api.utils.password import hash_password


@pytest.mark.asyncio
async def test_create_ticket_success(pg_async_session):
    """Test successfully creating a ticket with valid data."""
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

    # Create ticket
    ticket_data = TicketCreateRequest(
        title="Test Ticket",
        description="This is a test ticket",
        project_id=str(project.id),
        priority="high",
        status="open",
    )

    ticket = await create_ticket(session, ticket_data, user)

    assert ticket.id is not None
    assert ticket.title == "Test Ticket"
    assert ticket.description == "This is a test ticket"
    assert ticket.project_id == project.id
    assert ticket.organization_id == org.id
    assert ticket.created_by == user.id
    assert ticket.priority == "high"
    assert ticket.status == "open"
    assert ticket.assigned_to is None


@pytest.mark.asyncio
async def test_create_ticket_with_assigned_user(pg_async_session):
    """Test creating a ticket with an assigned user."""
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

    # Create ticket with assigned user
    ticket_data = TicketCreateRequest(
        title="Assigned Ticket",
        description="This ticket is assigned",
        project_id=str(project.id),
        assigned_to=str(assignee.id),
        priority="medium",
    )

    ticket = await create_ticket(session, ticket_data, creator)

    assert ticket.assigned_to == assignee.id
    assert ticket.created_by == creator.id


@pytest.mark.asyncio
async def test_create_ticket_invalid_project_id(pg_async_session):
    """Test creating a ticket with invalid project ID format."""
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
    )
    session.add(user)
    await session.flush()
    await session.commit()

    # Try to create ticket with invalid project ID
    ticket_data = TicketCreateRequest(
        title="Test Ticket",
        description="This is a test ticket",
        project_id="invalid-uuid",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_ticket(session, ticket_data, user)

    assert exc_info.value.status_code == 400
    assert "Invalid project ID format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_ticket_nonexistent_project(pg_async_session):
    """Test creating a ticket with a project that doesn't exist."""
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
    )
    session.add(user)
    await session.flush()
    await session.commit()

    # Try to create ticket with nonexistent project
    fake_project_id = str(uuid.uuid4())
    ticket_data = TicketCreateRequest(
        title="Test Ticket",
        description="This is a test ticket",
        project_id=fake_project_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_ticket(session, ticket_data, user)

    assert exc_info.value.status_code == 404
    assert "Project not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_ticket_project_different_organization(pg_async_session):
    """Test creating a ticket for a project in a different organization."""
    session = pg_async_session

    # Create first organization with user
    org1 = Organization(name="Org 1", industry="Tech")
    session.add(org1)
    await session.flush()

    role1 = Role(
        name="admin",
        organization_id=org1.id,
        description="Admin role",
        permissions={},
    )
    session.add(role1)
    await session.flush()

    user1 = User(
        organization_id=org1.id,
        role_id=role1.id,
        email="user1@company.com",
        hashed_password=hash_password("Test@1234"),
        name="User 1",
        auth_provider="local",
        is_active=True,
    )
    session.add(user1)
    await session.flush()

    # Create second organization with project
    org2 = Organization(name="Org 2", industry="Finance")
    session.add(org2)
    await session.flush()

    project2 = Project(
        organization_id=org2.id,
        name="Org 2 Project",
        description="A project in org 2",
        is_active=True,
    )
    session.add(project2)
    await session.flush()
    await session.commit()

    # Try to create ticket in org2's project as user from org1
    ticket_data = TicketCreateRequest(
        title="Cross-org Ticket",
        description="Should fail",
        project_id=str(project2.id),
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_ticket(session, ticket_data, user1)

    assert exc_info.value.status_code == 404
    assert "Project not found or access denied" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_ticket_invalid_assigned_user(pg_async_session):
    """Test creating a ticket with invalid assigned user ID format."""
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

    # Try to create ticket with invalid assigned user ID
    ticket_data = TicketCreateRequest(
        title="Test Ticket",
        description="This is a test ticket",
        project_id=str(project.id),
        assigned_to="invalid-uuid",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_ticket(session, ticket_data, user)

    assert exc_info.value.status_code == 400
    assert "Invalid assigned user ID format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_ticket_assigned_user_different_organization(pg_async_session):
    """Test creating a ticket with an assigned user from a different organization."""
    session = pg_async_session

    # Create first organization
    org1 = Organization(name="Org 1", industry="Tech")
    session.add(org1)
    await session.flush()

    role1 = Role(
        name="admin",
        organization_id=org1.id,
        description="Admin role",
        permissions={},
    )
    session.add(role1)
    await session.flush()

    user1 = User(
        organization_id=org1.id,
        role_id=role1.id,
        email="user1@company.com",
        hashed_password=hash_password("Test@1234"),
        name="User 1",
        auth_provider="local",
        is_active=True,
    )
    session.add(user1)
    await session.flush()

    project1 = Project(
        organization_id=org1.id,
        name="Project 1",
        description="A project in org 1",
        is_active=True,
    )
    session.add(project1)
    await session.flush()

    # Create second organization with user
    org2 = Organization(name="Org 2", industry="Finance")
    session.add(org2)
    await session.flush()

    role2 = Role(
        name="admin",
        organization_id=org2.id,
        description="Admin role",
        permissions={},
    )
    session.add(role2)
    await session.flush()

    user2 = User(
        organization_id=org2.id,
        role_id=role2.id,
        email="user2@company.com",
        hashed_password=hash_password("Test@1234"),
        name="User 2",
        auth_provider="local",
        is_active=True,
    )
    session.add(user2)
    await session.flush()
    await session.commit()

    # Try to assign ticket to user from different org
    ticket_data = TicketCreateRequest(
        title="Cross-org Assignment",
        description="Should fail",
        project_id=str(project1.id),
        assigned_to=str(user2.id),
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_ticket(session, ticket_data, user1)

    assert exc_info.value.status_code == 404
    assert "Assigned user not found or access denied" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_ticket_by_id_success(pg_async_session):
    """Test retrieving a ticket by ID."""
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

    # Create ticket
    ticket_data = TicketCreateRequest(
        title="Test Ticket",
        description="This is a test ticket",
        project_id=str(project.id),
    )

    created_ticket = await create_ticket(session, ticket_data, user)

    # Retrieve ticket
    retrieved_ticket = await get_ticket_by_id(session, created_ticket.id, org.id)

    assert retrieved_ticket is not None
    assert retrieved_ticket.id == created_ticket.id
    assert retrieved_ticket.title == "Test Ticket"


@pytest.mark.asyncio
async def test_get_ticket_by_id_wrong_organization(pg_async_session):
    """Test retrieving a ticket from a different organization returns None."""
    session = pg_async_session

    # Create first organization
    org1 = Organization(name="Org 1", industry="Tech")
    session.add(org1)
    await session.flush()

    role1 = Role(
        name="admin",
        organization_id=org1.id,
        description="Admin role",
        permissions={},
    )
    session.add(role1)
    await session.flush()

    user1 = User(
        organization_id=org1.id,
        role_id=role1.id,
        email="user1@company.com",
        hashed_password=hash_password("Test@1234"),
        name="User 1",
        auth_provider="local",
        is_active=True,
    )
    session.add(user1)
    await session.flush()

    project1 = Project(
        organization_id=org1.id,
        name="Project 1",
        description="A project in org 1",
        is_active=True,
    )
    session.add(project1)
    await session.flush()
    await session.commit()

    # Create second organization
    org2 = Organization(name="Org 2", industry="Finance")
    session.add(org2)
    await session.flush()
    await session.commit()

    # Create ticket in org1
    ticket_data = TicketCreateRequest(
        title="Org 1 Ticket",
        description="A ticket in org 1",
        project_id=str(project1.id),
    )

    created_ticket = await create_ticket(session, ticket_data, user1)

    # Try to retrieve from org2
    retrieved_ticket = await get_ticket_by_id(session, created_ticket.id, org2.id)

    assert retrieved_ticket is None
