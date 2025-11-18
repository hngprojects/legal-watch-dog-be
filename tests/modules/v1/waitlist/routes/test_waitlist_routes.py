import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
import pytest_asyncio
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router
from app.api.modules.v1.waitlist.schemas.waitlist_schema import WaitlistSignup
from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.db.database import get_db, AsyncSessionLocal, engine


@pytest_asyncio.fixture
async def test_session():
    """Provide a clean test database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
def app():
    """Provide FastAPI app instance with the waitlist router included."""
    app = FastAPI()
    app.include_router(waitlist_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_signup_waitlist_success(app, test_session):
    """Test that a new email can sign up successfully."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    payload = WaitlistSignup(
        organization_email="success@company.com",
        organization_name="Success Company"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "Successfully added to waitlist" in data["message"]


@pytest_asyncio.fixture
async def test_signup_waitlist_duplicate_email(app, test_session):
    """Test that signing up with an existing email returns an error."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    entry = Waitlist(
        organization_email="dup@company.com",
        organization_name="Dup Company"
    )
    test_session.add(entry)
    await test_session.commit()

    payload = WaitlistSignup(
        organization_email="dup@company.com",
        organization_name="Dup Company"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "fail"
    assert "Email already registered" in data["message"]
