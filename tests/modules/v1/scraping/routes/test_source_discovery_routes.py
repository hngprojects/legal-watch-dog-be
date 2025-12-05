"""
Integration tests for Source Discovery API routes.

Tests AI source suggestion and acceptance endpoints.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.scraping.models.source_model import Source, SourceType
from app.api.modules.v1.users.models.users_model import User
from main import app


@pytest.fixture
def sample_user():
    """Fixture for an authenticated user."""
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
    )


@pytest_asyncio.fixture
async def sample_jurisdiction_id(pg_async_session):
    """Fixture for a sample jurisdiction UUID."""
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project

    organization = Organization(name="Test Organization")
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    project = Project(
        org_id=organization.id,
        title="Test Project",
        description="Test description",
        master_prompt="Collect latest regulations",
    )
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Jurisdiction",
        description="Test description",
        prompt="Focus on legal updates",
    )
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    return jurisdiction.id


@pytest.fixture
def auth_headers(sample_user):
    """Fixture for authentication headers."""
    return {"Authorization": "Bearer mock_valid_token"}


@pytest_asyncio.fixture
async def client():
    """Fixture for FastAPI async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


class TestAcceptSuggestedSourcesEndpoint:
    """Tests for POST /sources/accept-suggestions"""

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful acceptance of AI-suggested sources."""

        payload = {
            "suggested_sources": [
                {
                    "title": "Supreme Court Opinions",
                    "url": "https://supremecourt.gov/opinions",
                    "snippet": "Official court opinions and decisions",
                    "confidence_reason": "Government domain with official content",
                    "is_official": True,
                },
                {
                    "title": "Federal Register",
                    "url": "https://federalregister.gov",
                    "snippet": "Official publication of federal regulations",
                    "confidence_reason": "Official government publication",
                    "is_official": True,
                },
            ],
            "jurisdiction_id": str(sample_jurisdiction_id),
            "source_type": "web",
            "scrape_frequency": "DAILY",
            "scraping_rules": {"selector": ".content"},
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["status_code"] == 201
        assert "Suggested sources accepted and created successfully" in data["message"]
        assert "sources" in data["data"]
        assert data["data"]["count"] == 2
        assert len(data["data"]["sources"]) == 2
        assert data["data"]["sources"][0]["name"] == "Supreme Court Opinions"
        assert data["data"]["sources"][1]["name"] == "Federal Register"

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_empty_list(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test acceptance with empty suggested sources list."""

        payload = {
            "suggested_sources": [],
            "jurisdiction_id": str(sample_jurisdiction_id),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["count"] == 0
        assert data["data"]["sources"] == []

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_duplicate_url(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test acceptance fails when duplicate URLs exist."""

        # First create a source with duplicate URL (normalize with HttpUrl like the API does)
        from pydantic import HttpUrl

        existing_source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Existing Source",
            url=str(HttpUrl("https://duplicate.gov")),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(existing_source)
        await pg_async_session.commit()

        payload = {
            "suggested_sources": [
                {
                    "title": "Duplicate Source",
                    "url": "https://duplicate.gov",  # Duplicate URL
                    "snippet": "This will fail",
                    "confidence_reason": "Test",
                    "is_official": True,
                }
            ],
            "jurisdiction_id": str(sample_jurisdiction_id),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400, got {response.status_code}: {response.json()}"
        )
        data = response.json()

        assert "already exist" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_invalid_data(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test acceptance with invalid suggested source data."""

        payload = {
            "suggested_sources": [
                {
                    "title": "",
                    "url": "not-a-valid-url",
                    "snippet": "Test",
                    "confidence_reason": "Test",
                    "is_official": True,
                }
            ],
            "jurisdiction_id": str(uuid.uuid4()),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_unauthorized(self, client, pg_async_session):
        """Test that unauthenticated acceptance requests are rejected."""

        payload = {
            "suggested_sources": [
                {
                    "title": "Test Source",
                    "url": "https://example.com",
                    "snippet": "Test snippet",
                    "confidence_reason": "Test reason",
                    "is_official": True,
                }
            ],
            "jurisdiction_id": str(uuid.uuid4()),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        app.dependency_overrides.clear()

        response = await client.post("/api/v1/sources/accept-suggestions", json=payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN
