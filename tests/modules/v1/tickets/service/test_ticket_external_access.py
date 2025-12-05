from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.api.modules.v1.tickets.models.ticket_external_access_model import (
    TicketExternalAccess,
)
from app.api.modules.v1.tickets.service.ticket_external_access_service import (
    TicketExternalAccessService,
)


@pytest.mark.asyncio
async def test_create_external_access_success(db_session, sample_ticket, sample_user):
    """Test successful creation of external access token."""
    service = TicketExternalAccessService(db_session)

    result = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        email="external@partner.com",
        expires_in_days=30,
    )

    assert result.ticket_id == str(sample_ticket.id)
    assert result.token.startswith("ext_")
    assert result.email == "external@partner.com"
    assert result.is_active is True
    assert result.access_count == 0
    assert result.expires_at is not None
    assert "external/tickets/" in result.access_url


@pytest.mark.asyncio
async def test_create_external_access_no_expiration(db_session, sample_ticket, sample_user):
    """Test creating external access without expiration."""
    service = TicketExternalAccessService(db_session)

    result = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        email=None,
        expires_in_days=None,
    )

    assert result.expires_at is None
    assert result.email is None


@pytest.mark.asyncio
async def test_get_ticket_by_token_success(db_session, sample_ticket, sample_user):
    """Test retrieving ticket with valid token."""
    service = TicketExternalAccessService(db_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    result = await service.get_ticket_by_token(token=access.token)

    assert result.id == str(sample_ticket.id)
    assert result.title == sample_ticket.title
    assert result.description == sample_ticket.description
    assert result.status == sample_ticket.status.value
    assert result.priority == sample_ticket.priority.value


@pytest.mark.asyncio
async def test_get_ticket_by_token_tracks_access(db_session, sample_ticket, sample_user):
    """Test that accessing ticket updates tracking metrics."""
    service = TicketExternalAccessService(db_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    await service.get_ticket_by_token(token=access.token)
    await service.get_ticket_by_token(token=access.token)

    accesses = await service.list_external_accesses(ticket_id=sample_ticket.id)
    assert accesses[0].access_count == 2
    assert accesses[0].last_accessed_at is not None


@pytest.mark.asyncio
async def test_get_ticket_by_invalid_token(db_session):
    """Test that invalid token raises error."""
    service = TicketExternalAccessService(db_session)

    with pytest.raises(ValueError, match="Invalid access token"):
        await service.get_ticket_by_token(token="invalid_token_123")


@pytest.mark.asyncio
async def test_get_ticket_by_revoked_token(db_session, sample_ticket, sample_user):
    """Test that revoked token cannot access ticket."""
    service = TicketExternalAccessService(db_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    await service.revoke_external_access(
        access_id=uuid4(access.id),
        current_user_id=sample_user.id,
    )

    with pytest.raises(ValueError, match="revoked"):
        await service.get_ticket_by_token(token=access.token)


@pytest.mark.asyncio
async def test_get_ticket_by_expired_token(db_session, sample_ticket, sample_user):
    """Test that expired token cannot access ticket."""
    service = TicketExternalAccessService(db_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
        expires_in_days=1,
    )

    from sqlmodel import select

    stmt = select(TicketExternalAccess).where(TicketExternalAccess.token == access.token)
    result = await db_session.execute(stmt)
    db_access = result.scalar_one()
    db_access.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    with pytest.raises(ValueError, match="expired"):
        await service.get_ticket_by_token(token=access.token)


@pytest.mark.asyncio
async def test_revoke_external_access(db_session, sample_ticket, sample_user):
    """Test revoking external access."""
    service = TicketExternalAccessService(db_session)

    access = await service.create_external_access(
        ticket_id=sample_ticket.id,
        created_by_user_id=sample_user.id,
    )

    result = await service.revoke_external_access(
        access_id=uuid4(access.id),
        current_user_id=sample_user.id,
    )

    assert result is True

    accesses = await service.list_external_accesses(ticket_id=sample_ticket.id)
    assert accesses[0].is_active is False
    assert accesses[0].revoked_at is not None


@pytest.mark.asyncio
async def test_list_external_accesses(db_session, sample_ticket, sample_user):
    """Test listing all external accesses for a ticket."""
    service = TicketExternalAccessService(db_session)

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
    assert accesses[1].email in ["user1@partner.com", "user2@partner.com"]


@pytest.mark.asyncio
async def test_token_uniqueness(db_session, sample_ticket, sample_user):
    """Test that generated tokens are unique."""
    service = TicketExternalAccessService(db_session)

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
    assert len(access2.token) > 50
