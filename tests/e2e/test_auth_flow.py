import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.api.core.config import settings
from main import app
from app.api.modules.v1.auth.schemas.register import RegisterRequest, OTPVerifyRequest
from app.api.modules.v1.auth.schemas.login import LoginRequest
import json

# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create test database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with test database"""
    # Override the database dependency
    from app.api.db.database import get_db

    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_e2e_company_registration_to_login(client, mock_redis):
    """Test end-to-end flow: register company -> verify OTP -> login"""

    # Test data
    register_data = {
        "name": "Test Company",
        "email": "admin@testcompany.com",
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
        "industry": "Technology"
    }

    # 1. Register company
    response = client.post("/auth/register", json=register_data)
    assert response.status_code == 201
    register_response = response.json()
    assert "access_token" in register_response
    assert register_response["message"] == "Registration successful. Verify the OTP sent to your email."

    # 2. Get OTP from mock Redis (since it's stored in redis_store)
    # The OTP is stored with key str(user.id), but we need user.id
    # Since it's test, we can assume the OTP is generated, but to get it, we need to find the user
    # For simplicity, since OTP.generate_code() creates 6-digit, and stored in redis_store
    # But to make it work, perhaps patch the store_otp to capture the code

    # Actually, since mock_redis uses redis_store dict, and store_otp calls setex with key=str(user.id), value=otp_code
    # But user.id is not known yet. In test, we can mock the send_email to capture the OTP

    # Better way: patch send_email to capture the context
    otp_code = None

    def mock_send_email(context):
        nonlocal otp_code
        otp_code = context["otp"]

    # Patch send_email
    import app.api.core.dependencies.send_mail as mail_module
    original_send_email = mail_module.send_email
    mail_module.send_email = mock_send_email

    try:
        # Re-register to capture OTP
        response = client.post("/auth/register", json=register_data)
        assert response.status_code == 201

        # Now otp_code should be set
        assert otp_code is not None
        assert len(otp_code) == 6

        # 3. Verify OTP
        verify_data = {
            "email": register_data["email"],
            "code": otp_code
        }
        response = client.post("/auth/verify-otp", json=verify_data)
        assert response.status_code == 200
        verify_response = response.json()
        assert "message" in verify_response
        assert "OTP verified successfully" in verify_response["message"]

        # 4. Login
        login_data = {
            "email": register_data["email"],
            "password": register_data["password"]
        }
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        login_response = response.json()
        assert "access_token" in login_response
        assert "refresh_token" in login_response
        assert login_response["token_type"] == "bearer"

    finally:
        # Restore original send_email
        mail_module.send_email = original_send_email