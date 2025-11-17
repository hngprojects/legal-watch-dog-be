import pytest
import pytest_asyncio
from httpx import AsyncClient
try:
    from httpx import ASGITransport
except ImportError:
    ASGITransport = None
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from fastapi import FastAPI

from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.modules.v1.waitlist.service.waitlist_service import waitlist_service
from app.api.db.database import get_db


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a fresh database for each test"""
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
def app():
    """Create FastAPI app instance with all routes"""
    from main import app as main_app
    # Force reload routes to ensure they're registered
    return main_app


@pytest_asyncio.fixture
async def client(app, test_db):
    """Create test client with database override"""
    # Override the database dependency
    async def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Use different syntax based on httpx version
    if ASGITransport is not None:
        # httpx >= 0.24
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    else:
        # httpx < 0.24
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    # Clean up
    app.dependency_overrides.clear()


# ============================================
# SERVICE LAYER TESTS
# ============================================

class TestWaitlistService:
    """Test the WaitlistService business logic"""
    
    @pytest.mark.asyncio
    async def test_add_to_waitlist_success(self, test_db):
        """Test successfully adding an organization to waitlist"""
        result = await waitlist_service.add_to_waitlist(
            test_db,
            "test@example.com",
            "Test Organization"
        )
        
        assert result.success is True
        assert result.organization_email == "test@example.com"
        assert result.organization_name == "Test Organization"
        assert "successfully added" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_add_to_waitlist_email_lowercase(self, test_db):
        """Test that emails are converted to lowercase"""
        result = await waitlist_service.add_to_waitlist(
            test_db,
            "TEST@EXAMPLE.COM",
            "Test Organization"
        )
        
        assert result.organization_email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_add_to_waitlist_duplicate_email(self, test_db):
        """Test that duplicate emails are rejected"""
        # Add first entry
        await waitlist_service.add_to_waitlist(
            test_db,
            "test@example.com",
            "Test Organization"
        )
        
        # Try to add duplicate
        with pytest.raises(Exception) as exc_info:
            await waitlist_service.add_to_waitlist(
                test_db,
                "test@example.com",
                "Another Organization"
            )
        
        assert exc_info.value.status_code == 400
        assert "already registered" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_add_to_waitlist_strips_whitespace(self, test_db):
        """Test that whitespace is stripped from inputs"""
        result = await waitlist_service.add_to_waitlist(
            test_db,
            "  test@example.com  ",
            "  Test Organization  "
        )
        
        assert result.organization_email == "test@example.com"
        assert result.organization_name == "Test Organization"
    
    @pytest.mark.asyncio
    async def test_email_exists_returns_true_for_existing(self, test_db):
        """Test _email_exists returns True for existing email"""
        # Add entry
        await waitlist_service.add_to_waitlist(
            test_db,
            "test@example.com",
            "Test Organization"
        )
        
        # Check if exists
        exists = await waitlist_service._email_exists(test_db, "test@example.com")
        assert exists is True
    
    @pytest.mark.asyncio
    async def test_email_exists_returns_false_for_new(self, test_db):
        """Test _email_exists returns False for new email"""
        exists = await waitlist_service._email_exists(test_db, "new@example.com")
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_email_exists_case_insensitive(self, test_db):
        """Test _email_exists is case insensitive"""
        # Add lowercase
        await waitlist_service.add_to_waitlist(
            test_db,
            "test@example.com",
            "Test Organization"
        )
        
        # Check with uppercase
        exists = await waitlist_service._email_exists(test_db, "TEST@EXAMPLE.COM")
        assert exists is True


# ============================================
# API ENDPOINT TESTS
# ============================================

class TestWaitlistEndpoints:
    """Test the waitlist API endpoints"""
    
    @pytest.mark.asyncio
    async def test_debug_routes(self, app):
        """Debug: Print all available routes"""
        print("\n=== Available Routes ===")
        for route in app.routes:
            if hasattr(route, "path"):
                methods = getattr(route, "methods", [])
                print(f"{list(methods) if methods else ['N/A']} {route.path}")
        print("========================\n")
    
    @pytest.mark.asyncio
    async def test_signup_success(self, client):
        """Test successful signup via API"""
        response = await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": "Test Organization"
            }
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.json()}"
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_signup_invalid_email(self, client):
        """Test signup with invalid email format"""
        response = await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "not-an-email",
                "organization_name": "Test Organization"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_signup_missing_fields(self, client):
        """Test signup with missing required fields"""
        response = await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com"
                # Missing organization_name
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_signup_duplicate_email(self, client):
        """Test signup with duplicate email"""
        # First signup
        await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": "Test Organization"
            }
        )
        
        # Duplicate signup
        response = await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": "Another Organization"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "already registered" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_signup_case_insensitive_duplicate(self, client):
        """Test that duplicate checking is case insensitive"""
        # First signup (lowercase)
        await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": "Test Organization"
            }
        )
        
        # Duplicate with uppercase
        response = await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "TEST@EXAMPLE.COM",
                "organization_name": "Another Organization"
            }
        )
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_signup_empty_organization_name(self, client):
        """Test signup with empty organization name"""
        response = await client.post(
            "/api/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": ""
            }
        )
        
        # Should either fail validation or be accepted (depending on your requirements)
        assert response.status_code in [201, 422]


# ============================================
# MODEL TESTS
# ============================================

class TestWaitlistModel:
    """Test the Waitlist database model"""
    
    @pytest.mark.asyncio
    async def test_create_waitlist_entry(self, test_db):
        """Test creating a waitlist entry in database"""
        entry = Waitlist(
            organization_email="test@example.com",
            organization_name="Test Organization"
        )
        
        test_db.add(entry)
        await test_db.commit()
        await test_db.refresh(entry)
        
        assert entry.id is not None
        assert entry.organization_email == "test@example.com"
        assert entry.organization_name == "Test Organization"
        assert entry.created_at is not None
    
    @pytest.mark.asyncio
    async def test_unique_email_constraint(self, test_db):
        """Test that email uniqueness is enforced"""
        # Create first entry
        entry1 = Waitlist(
            organization_email="test@example.com",
            organization_name="Organization 1"
        )
        test_db.add(entry1)
        await test_db.commit()
        
        # Try to create duplicate
        entry2 = Waitlist(
            organization_email="test@example.com",
            organization_name="Organization 2"
        )
        test_db.add(entry2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            await test_db.commit()
    
    @pytest.mark.asyncio
    async def test_auto_increment_id(self, test_db):
        """Test that IDs are auto-incremented"""
        entry1 = Waitlist(
            organization_email="test1@example.com",
            organization_name="Organization 1"
        )
        entry2 = Waitlist(
            organization_email="test2@example.com",
            organization_name="Organization 2"
        )
        
        test_db.add(entry1)
        test_db.add(entry2)
        await test_db.commit()
        await test_db.refresh(entry1)
        await test_db.refresh(entry2)
        
        assert entry1.id is not None
        assert entry2.id is not None
        assert entry2.id > entry1.id
    
    @pytest.mark.asyncio
    async def test_created_at_auto_set(self, test_db):
        """Test that created_at is automatically set"""
        from datetime import datetime, timezone, timedelta
        
        entry = Waitlist(
            organization_email="test@example.com",
            organization_name="Test Organization"
        )
        
        test_db.add(entry)
        await test_db.commit()
        await test_db.refresh(entry)
        
        assert entry.created_at is not None
        
        # Make both datetimes timezone-aware for comparison
        now = datetime.now(timezone.utc)
        
        # Handle both timezone-aware and naive datetimes
        if entry.created_at.tzinfo is None:
            # If stored datetime is naive, make it aware (assume UTC)
            created_at = entry.created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = entry.created_at
        
        # Check it's a recent timestamp (within last minute)
        time_diff = now - created_at
        assert time_diff < timedelta(minutes=1), f"Time difference too large: {time_diff}"
        assert time_diff >= timedelta(0), "Created time is in the future"


# ============================================
# INTEGRATION TESTS
# ============================================

class TestWaitlistIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_multiple_signups(self, client):
        """Test multiple different organizations can sign up"""
        organizations = [
            ("org1@example.com", "Organization 1"),
            ("org2@example.com", "Organization 2"),
            ("org3@example.com", "Organization 3"),
        ]
        
        for email, name in organizations:
            response = await client.post(
                "/v1/waitlist/signup",
                json={
                    "organization_email": email,
                    "organization_name": name
                }
            )
            assert response.status_code == 201
    
    @pytest.mark.asyncio
    async def test_signup_with_special_characters_in_name(self, client):
        """Test signup with special characters in organization name"""
        response = await client.post(
            "/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": "Test & Co., Ltd. (2024)"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["data"]["organization_name"] == "Test & Co., Ltd. (2024)"
    
    @pytest.mark.asyncio
    async def test_signup_with_international_email(self, client):
        """Test signup with international email domains"""
        response = await client.post(
            "/v1/waitlist/signup",
            json={
                "organization_email": "test@example.co.uk",
                "organization_name": "UK Organization"
            }
        )
        
        assert response.status_code == 201


# ============================================
# EDGE CASE TESTS
# ============================================

class TestWaitlistEdgeCases:
    """Test edge cases and boundary conditions"""
    
    @pytest.mark.asyncio
    async def test_very_long_organization_name(self, client):
        """Test with very long organization name"""
        long_name = "A" * 300  # Longer than max_length
        
        response = await client.post(
            "/v1/waitlist/signup",
            json={
                "organization_email": "test@example.com",
                "organization_name": long_name
            }
        )
        
        # Should either truncate or reject
        assert response.status_code in [201, 422]
    
    @pytest.mark.asyncio
    async def test_email_with_plus_addressing(self, client):
        """Test email with plus addressing (user+tag@example.com)"""
        response = await client.post(
            "/v1/waitlist/signup",
            json={
                "organization_email": "user+test@example.com",
                "organization_name": "Test Organization"
            }
        )
        
        assert response.status_code == 201
    
    @pytest.mark.asyncio
    async def test_concurrent_signups_same_email(self, client):
        """Test concurrent signup attempts with same email"""
        import asyncio
        
        async def signup():
            return await client.post(
                "/v1/waitlist/signup",
                json={
                    "organization_email": "test@example.com",
                    "organization_name": "Test Organization"
                }
            )
        
        # Try two concurrent signups
        results = await asyncio.gather(
            signup(),
            signup(),
            return_exceptions=True
        )
        
        # One should succeed (201), one should fail (400)
        status_codes = [r.status_code for r in results if hasattr(r, 'status_code')]
        assert 201 in status_codes
        assert 400 in status_codes or len(status_codes) == 1