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


class TestUser:
    """Test cases for User model."""

    @pytest.fixture(name="organization")
    def organization_fixture(self, session: Session):
        """Create a test organization."""
        org = Organization(name="Test Org")
        session.add(org)
        session.commit()
        session.refresh(org)
        return org

    @pytest.fixture(name="role")
    def role_fixture(self, session: Session):
        """Create a test role."""
        role = Role(name="user")
        session.add(role)
        session.commit()
        session.refresh(role)
        return role

    def test_create_user(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test creating a basic user."""
        user = User(
            email="test@example.com",
            hashed_password="hashed_password_here",
            name="Test User",
            organization_id=organization.id,
            role_id=role.id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.is_active is True
        assert user.is_verified is False
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    def test_user_relationships(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test user relationships with organization and role."""
        user = User(
            email="rel@example.com",
            hashed_password="hashed",
            name="Rel User",
            organization_id=organization.id,
            role_id=role.id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.organization.id == organization.id
        assert user.organization.name == organization.name
        assert user.role.id == role.id
        assert user.role.name == role.name

    def test_user_unique_email(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test that user emails must be unique."""
        user1 = User(
            email="unique@example.com",
            hashed_password="hash1",
            name="User 1",
            organization_id=organization.id,
            role_id=role.id,
        )
        session.add(user1)
        session.commit()

        user2 = User(
            email="unique@example.com",
            hashed_password="hash2",
            name="User 2",
            organization_id=organization.id,
            role_id=role.id,
        )
        session.add(user2)

        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            session.commit()

    def test_user_inactive(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test creating an inactive user."""
        user = User(
            email="inactive@example.com",
            hashed_password="hash",
            name="Inactive User",
            organization_id=organization.id,
            role_id=role.id,
            is_active=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.is_active is False

    def test_user_verified(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test creating a verified user."""
        user = User(
            email="verified@example.com",
            hashed_password="hash",
            name="Verified User",
            organization_id=organization.id,
            role_id=role.id,
            is_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.is_verified is True

    def test_organization_users_relationship(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test the back-relationship from organization to users."""
        user1 = User(
            email="user1@example.com",
            hashed_password="hash",
            name="User 1",
            organization_id=organization.id,
            role_id=role.id,
        )
        user2 = User(
            email="user2@example.com",
            hashed_password="hash",
            name="User 2",
            organization_id=organization.id,
            role_id=role.id,
        )
        session.add(user1)
        session.add(user2)
        session.commit()
        session.refresh(organization)

        assert len(organization.users) == 2
        assert user1 in organization.users
        assert user2 in organization.users

    def test_role_users_relationship(
        self, session: Session, organization: Organization, role: Role
    ):
        """Test the back-relationship from role to users."""
        user1 = User(
            email="role1@example.com",
            hashed_password="hash",
            name="Role User 1",
            organization_id=organization.id,
            role_id=role.id,
        )
        user2 = User(
            email="role2@example.com",
            hashed_password="hash",
            name="Role User 2",
            organization_id=organization.id,
            role_id=role.id,
        )
        session.add(user1)
        session.add(user2)
        session.commit()
        session.refresh(role)

        assert len(role.users) == 2
        assert user1 in role.users
        assert user2 in role.users
