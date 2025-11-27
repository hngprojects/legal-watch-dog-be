import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
<<<<<<< HEAD
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router
from app.api.modules.v1.waitlist.schemas.waitlist_schema import WaitlistSignup
from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.db.database import get_db, AsyncSessionLocal, engine


# -----------------------------
# Async test DB session fixture
# -----------------------------
@pytest.fixture
async def test_session():
    """Provide a clean test database session for each test."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session  # <-- provide session to test

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


# -----------------------------
# FastAPI app fixture
# -----------------------------
@pytest.fixture
def app():
    """Provide FastAPI app instance with the waitlist router included."""
    app = FastAPI()
    app.include_router(waitlist_router, prefix="/api/v1")
    return app


# -----------------------------
# Test: successful signup
# -----------------------------
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


# -----------------------------
# Test: duplicate email signup
# -----------------------------
@pytest.mark.asyncio
async def test_signup_waitlist_duplicate_email(app, test_session):
    """Test that signing up with an existing email returns an error."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    # Pre-insert a duplicate email
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
=======
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router
from app.api.modules.v1.waitlist.schemas.waitlist_schema import WaitlistSignup


@pytest.fixture
def app(pg_async_session: AsyncSession):
    """FastAPI app with test DB dependency override."""
    app = FastAPI()
    app.include_router(waitlist_router, prefix="/api/v1")

    async def override_get_db():
        yield pg_async_session

    from app.api.db.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.mark.asyncio
async def test_signup_waitlist_success(app, pg_async_session):
    """Test successful waitlist signup."""
    payload = WaitlistSignup(
        organization_email="success@company.com", organization_name="Success Company"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "Successfully added to waitlist" in data["message"]


@pytest.mark.asyncio
async def test_signup_waitlist_duplicate_email(app, pg_async_session):
    """Test signing up with an existing email returns error."""

    entry = Waitlist(organization_email="dup@company.com", organization_name="Dup Company")
    pg_async_session.add(entry)
    await pg_async_session.commit()

    payload = WaitlistSignup(organization_email="dup@company.com", organization_name="Dup Company")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "ERROR"
    assert "Email already registered" in data["message"]
    assert isinstance(data["errors"], dict)
>>>>>>> fix/billing-model-cleanup
