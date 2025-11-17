import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.api.modules.v1.users.models import Role
from app.api.modules.v1.organization.models import Organization
from app.api.modules.v1.users.models import User
from app.api.core.config import settings


@pytest.fixture(name="session")
def session_fixture():
    """Create a fresh PostgreSQL session for each test."""
    engine = create_engine(settings.DATABASE_URL, echo=True)

    SQLModel.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

        SQLModel.metadata.drop_all(engine)


class TestRole:
    """Test cases for Role model."""

    def test_create_role(self, session: Session):
        """Test creating a basic role."""
        role = Role(name="admin", description="Administrator role")
        session.add(role)
        session.commit()
        session.refresh(role)

        assert role.id is not None
        assert isinstance(role.id, uuid.UUID)
        assert role.name == "admin"
        assert role.description == "Administrator role"
        assert role.permissions == {}
        assert isinstance(role.created_at, datetime)

    def test_role_with_permissions(self, session: Session):
        """Test role with custom permissions."""
        permissions = {
            "read": True,
            "write": True,
            "delete": False,
            "admin": True,
        }
        role = Role(name="editor", permissions=permissions)
        session.add(role)
        session.commit()
        session.refresh(role)

        assert role.permissions == permissions
        assert role.permissions["write"] is True
        assert role.permissions["delete"] is False

    def test_role_without_description(self, session: Session):
        """Test role without description."""
        role = Role(name="viewer")
        session.add(role)
        session.commit()
        session.refresh(role)

        assert role.description is None

    def test_role_unique_name(self, session: Session):
        """Test that role names must be unique."""
        role1 = Role(name="admin")
        session.add(role1)
        session.commit()

        role2 = Role(name="admin")
        session.add(role2)

        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            session.commit()
