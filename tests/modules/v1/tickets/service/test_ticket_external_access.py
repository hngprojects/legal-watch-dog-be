from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import pytest_asyncio
from sqlmodel import select

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.tickets.models.ticket_external_access_model import (
    TicketExternalAccess,
)
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketPriority, TicketStatus
from app.api.modules.v1.tickets.service.ticket_external_access_service import (
    TicketExternalAccessService,
)
from app.api.modules.v1.users.models.users_model import User


@pytest_asyncio.fixture
async def sample_user(pg_async_session):
    """Create a sample user for testing."""
    user = User(
        email="testuser@example.com",
        name="Test User",
        is_active=True,
        is_verified=True,
    )
    pg_async_session.add(user)
    await pg_async_session.commit()
    await pg_async_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_organization(pg_async_session):
    """Create a sample organization for testing."""
    org = Organization(name="Test Organization")
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def sample_project(pg_async_session, sample_organization):
    """Create a sample project for testing."""
    project = Project(
        title="Test Project",
        org_id=sample_organization.id,
        master_prompt="Test prompt",
    )
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def sample_ticket(pg_async_session, sample_user, sample_organization, sample_project):
    """Create a sample ticket for testing."""
    ticket = Ticket(
        title="Test Ticket",
        description="A test ticket for external access",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
        is_manual=True,
        created_by_user_id=sample_user.id,
        organization_id=sample_organization.id,
        project_id=sample_project.id,
    )
    pg_async_session.add(ticket)
    await pg_async_session.commit()
    await pg_async_session.refresh(ticket)
    return ticket


@pytest.mark.asyncio
async def test_create_external_access_with_expiration(pg_async_session, sample_ticket, sample_user):
    """Test creating external access with expiration."""
    service = TicketExternalAccessService(pg_async_session)

    result = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        email="external@partner.com",
        expires_in_days=30,
    )

    assert str(result.ticket_id) == str(sample_ticket.id)
    assert result.token.startswith("ext_")
    assert result.email == "external@partner.com"
    assert result.is_active is True
    assert result.expires_at is not None


@pytest.mark.asyncio
async def test_create_external_access_no_expiration(pg_async_session, sample_ticket, sample_user):
    """Test creating external access without expiration."""
    service = TicketExternalAccessService(pg_async_session)

    result = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    assert result.expires_at is None
    assert result.email is None


@pytest.mark.asyncio
async def test_get_ticket_by_token_success(pg_async_session, sample_ticket, sample_user):
    """Test retrieving ticket with valid token."""
    service = TicketExternalAccessService(pg_async_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    result = await service.get_ticket_by_token(token=access.token)

    assert result.id == str(sample_ticket.id)
    assert result.title == sample_ticket.title


@pytest.mark.asyncio
async def test_get_ticket_tracks_access_count(pg_async_session, sample_ticket, sample_user):
    """Test access count tracking."""
    service = TicketExternalAccessService(pg_async_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    await service.get_ticket_by_token(token=access.token)
    await service.get_ticket_by_token(token=access.token)

    accesses = await service.list_external_accesses(ticket_id=sample_ticket.id)
    assert accesses[0].access_count == 2


@pytest.mark.asyncio
async def test_get_ticket_by_invalid_token(pg_async_session):
    """Test invalid token raises error."""
    service = TicketExternalAccessService(pg_async_session)

    with pytest.raises(ValueError, match="Invalid access token"):
        await service.get_ticket_by_token(token="invalid_token_123")


@pytest.mark.asyncio
async def test_get_ticket_by_expired_token(pg_async_session, sample_ticket, sample_user):
    """Test expired token raises error."""
    service = TicketExternalAccessService(pg_async_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        expires_in_days=1,
    )

    stmt = select(TicketExternalAccess).where(TicketExternalAccess.token == access.token)
    result = await pg_async_session.execute(stmt)
    db_access = result.scalar_one()
    db_access.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await pg_async_session.commit()

    with pytest.raises(ValueError, match="expired"):
        await service.get_ticket_by_token(token=access.token)


@pytest.mark.asyncio
async def test_revoke_external_access(pg_async_session, sample_ticket, sample_user):
    """Test revoking external access."""
    service = TicketExternalAccessService(pg_async_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    access_uuid = UUID(access.id) if isinstance(access.id, str) else access.id
    result = await service.revoke_external_access(
        access_id=access_uuid,
        current_user_id=sample_user.id,
    )

    assert result is True


@pytest.mark.asyncio
async def test_access_revoked_token_fails(pg_async_session, sample_ticket, sample_user):
    """Test accessing revoked token raises error."""
    service = TicketExternalAccessService(pg_async_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    access_uuid = UUID(access.id) if isinstance(access.id, str) else access.id
    await service.revoke_external_access(
        access_id=access_uuid,
        current_user_id=sample_user.id,
    )

    with pytest.raises(ValueError, match="revoked"):
        await service.get_ticket_by_token(token=access.token)


@pytest.mark.asyncio
async def test_list_external_accesses(pg_async_session, sample_ticket, sample_user):
    """Test listing external accesses."""
    service = TicketExternalAccessService(pg_async_session)

    await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        email="user1@partner.com",
    )
    await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        email="user2@partner.com",
    )

    accesses = await service.list_external_accesses(ticket_id=sample_ticket.id)

    assert len(accesses) == 2
    assert accesses[0].email in ["user1@partner.com", "user2@partner.com"]


@pytest.mark.asyncio
async def test_token_uniqueness(pg_async_session, sample_ticket, sample_user):
    """Test generated tokens are unique."""
    service = TicketExternalAccessService(pg_async_session)

    access1 = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )
    access2 = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    assert access1.token != access2.token
    assert len(access1.token) > 50