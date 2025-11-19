import pytest
from datetime import datetime
from sqlmodel import SQLModel, select
from sqlalchemy.exc import IntegrityError

from app.api.modules.v1.waitlist.models.waitlist_model import (
    Waitlist,
    WaitlistSubscriber,
)
from app.api.db.database import AsyncSessionLocal, engine


@pytest.fixture(scope="module", autouse=True)
async def setup_database():
    """Create tables for test database."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield  # Run tests

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.mark.asyncio
async def test_create_waitlist_subscriber():
    """Test basic creation with organization."""
    async with AsyncSessionLocal() as session:
        # Create a waitlist organization first
        org = Waitlist(
            organization_email="org@example.com", organization_name="Example Org"
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)

        # Create subscriber linked to the organization
        subscriber = WaitlistSubscriber(
            email="test@example.com",
            name="John Doe",
            source="website",
            organization_email=org.organization_email,
        )
        session.add(subscriber)
        await session.commit()
        await session.refresh(subscriber)

        assert subscriber.email == "test@example.com"
        assert subscriber.name == "John Doe"
        assert subscriber.source == "website"
        assert isinstance(subscriber.signup_date, datetime)
        assert subscriber.organization_email == org.organization_email


@pytest.mark.asyncio
async def test_default_source_is_unknown():
    """Ensure default value is applied for subscriber source."""
    async with AsyncSessionLocal() as session:
        org = Waitlist(
            organization_email="default-org@example.com",
            organization_name="Default Org",
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)

        subscriber = WaitlistSubscriber(
            email="source-default@example.com",
            name="Jane Doe",
            organization_email=org.organization_email,
        )
        session.add(subscriber)
        await session.commit()
        await session.refresh(subscriber)

        assert subscriber.source == "unknown"


@pytest.mark.asyncio
async def test_email_must_be_unique():
    """Ensure unique constraint is enforced."""
    async with AsyncSessionLocal() as session:
        org = Waitlist(
            organization_email="unique-org@example.com", organization_name="Unique Org"
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)

        s1 = WaitlistSubscriber(
            email="unique@example.com",
            name="User One",
            organization_email=org.organization_email,
        )
        session.add(s1)
        await session.commit()

        s2 = WaitlistSubscriber(
            email="unique@example.com",
            name="User Two",
            organization_email=org.organization_email,
        )
        session.add(s2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_retrieve_waitlist_subscriber():
    """Test DB read/write cycle with organization."""
    async with AsyncSessionLocal() as session:
        org = Waitlist(
            organization_email="readwrite-org@example.com",
            organization_name="ReadWrite Org",
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)

        subscriber = WaitlistSubscriber(
            email="readwrite@example.com",
            name="Reader Writer",
            source="referral",
            organization_email=org.organization_email,
        )
        session.add(subscriber)
        await session.commit()
        await session.refresh(subscriber)

    async with AsyncSessionLocal() as session:
        result = await session.get(WaitlistSubscriber, "readwrite@example.com")
        assert result is not None
        assert result.name == "Reader Writer"
        assert result.source == "referral"
        assert result.organization_email == org.organization_email
