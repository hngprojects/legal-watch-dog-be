import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.api.modules.v1.organization.models import Organization
from app.api.modules.v1.users.models import Role
from app.api.modules.v1.users.models import User
from app.api.core.config import settings


@pytest.fixture(name="session")
def session_fixture():

    engine = create_engine(settings.DATABASE_URL, echo=True)

    SQLModel.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        SQLModel.metadata.drop_all(engine)


class TestOrganization:
    """Test cases for Organization model."""

    def test_create_organization(self, session: Session):
        """Test creating a basic organization."""
        org = Organization(name="Test Corp")
        session.add(org)
        session.commit()
        session.refresh(org)

        assert org.id is not None
        assert isinstance(org.id, uuid.UUID)
        assert org.name == "Test Corp"
        assert org.is_active is True
        assert org.settings == {}
        assert org.billing_info == {}
        assert isinstance(org.created_at, datetime)
        assert isinstance(org.updated_at, datetime)

    def test_organization_with_settings(self, session: Session):
        """Test organization with custom settings."""
        settings = {"theme": "dark", "notifications": True}
        org = Organization(name="Tech Inc", settings=settings)
        session.add(org)
        session.commit()
        session.refresh(org)

        assert org.settings == settings
        assert org.settings["theme"] == "dark"

    def test_organization_with_billing_info(self, session: Session):
        """Test organization with billing information."""
        billing = {"plan": "enterprise", "price": 99.99}
        org = Organization(name="Business LLC", billing_info=billing)
        session.add(org)
        session.commit()
        session.refresh(org)

        assert org.billing_info == billing
        assert org.billing_info["plan"] == "enterprise"

    def test_organization_inactive(self, session: Session):
        """Test creating an inactive organization."""
        org = Organization(name="Inactive Corp", is_active=False)
        session.add(org)
        session.commit()
        session.refresh(org)

        assert org.is_active is False

    def test_organization_timestamps(self, session: Session):
        """Test that timestamps are set correctly."""
        before = datetime.now(timezone.utc)
        org = Organization(name="Time Test")
        session.add(org)
        session.commit()
        session.refresh(org)
        after = datetime.now(timezone.utc)

        assert before <= org.created_at <= after
        assert before <= org.updated_at <= after
