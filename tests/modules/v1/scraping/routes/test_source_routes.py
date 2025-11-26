"""
Integration tests for Source API routes.

Tests all endpoints with authentication and database integration.
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

    # Create organization
    organization = Organization(name="Test Organization")
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    # Create project
    project = Project(org_id=organization.id, title="Test Project", description="Test description")
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    # Create jurisdiction
    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Jurisdiction",
        description="Test description",
    )
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    return jurisdiction.id


@pytest.fixture
def auth_headers(sample_user):
    """Fixture for authentication headers."""
    # Mock JWT token
    return {"Authorization": "Bearer mock_valid_token"}


@pytest_asyncio.fixture
async def client():
    """Fixture for FastAPI async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    # Clear any dependency overrides after test completes
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_source_success(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test successful source creation via API."""
    # Arrange
    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Test Ministry",
        "url": "https://ministry.gov.example",
        "source_type": "web",
        "scrape_frequency": "DAILY",
        "auth_details": {"username": "admin", "password": "secret"},
        "scraping_rules": {"selector": ".content"},
    }

    # Override dependencies
    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Act
    response = await client.post(
        "/api/v1/sources",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["status_code"] == 201
    assert data["message"] == "Source created successfully"
    assert "source" in data["data"]
    assert data["data"]["source"]["name"] == "Test Ministry"
    assert data["data"]["source"]["has_auth"] is True


@pytest.mark.asyncio
async def test_create_source_without_auth_details(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test creating source without authentication details."""
    # Arrange
    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Public Website",
        "url": "https://public.example.com",
        "source_type": "web",
        "scrape_frequency": "HOURLY",
    }

    # Override dependencies
    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Act
    response = await client.post(
        "/api/v1/sources",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["data"]["source"]["has_auth"] is False


@pytest.mark.asyncio
async def test_create_source_invalid_url(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test that invalid URLs are rejected."""
    # Arrange
    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Invalid Source",
        "url": "not-a-valid-url",
        "source_type": "web",
        "scrape_frequency": "DAILY",
    }

    # Override dependencies
    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Act
    response = await client.post(
        "/api/v1/sources",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_source_unauthorized(client, pg_async_session, sample_jurisdiction_id):
    """Test that unauthenticated requests are rejected."""
    # Arrange
    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Test Source",
        "url": "https://example.com",
    }

    # Clear any dependency overrides to ensure auth is required
    app.dependency_overrides.clear()

    # Act
    response = await client.post("/api/v1/sources", json=payload)

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
    """Tests for GET /sources"""

    @pytest.mark.asyncio
    async def test_get_sources_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful retrieval of sources list."""
        # Arrange - Create test sources
        source1 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 1",
            url="https://example1.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        source2 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 2",
            url="https://example2.com",
            source_type=SourceType.PDF,
            scrape_frequency="WEEKLY",
        )

        pg_async_session.add(source1)
        pg_async_session.add(source2)
        await pg_async_session.commit()

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.get(
            "/api/v1/sources",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Sources retrieved successfully"
        assert "sources" in data["data"]
        assert data["data"]["count"] >= 2

    @pytest.mark.asyncio
    async def test_get_sources_with_filters(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test get sources with jurisdiction filter."""

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.get(
            f"/api/v1/sources?jurisdiction_id={sample_jurisdiction_id}&is_active=true",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "sources" in data["data"]

    @pytest.mark.asyncio
    async def test_get_sources_pagination(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test pagination parameters."""

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.get(
            "/api/v1/sources?skip=0&limit=10",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK


class TestGetSourceEndpoint:
    """Tests for GET /sources/{source_id}"""

    @pytest.mark.asyncio
    async def test_get_source_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful retrieval of a single source."""
        # Arrange
        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Test Source",
            url="https://test.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
            auth_details_encrypted="encrypted_value",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.get(
            f"/api/v1/sources/{source.id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["source"]["id"] == str(source.id)
        assert data["data"]["source"]["name"] == "Test Source"
        assert data["data"]["source"]["has_auth"] is True
        # Ensure encrypted auth is NOT exposed
        assert "auth_details_encrypted" not in data["data"]["source"]

    @pytest.mark.asyncio
    async def test_get_source_not_found(self, client, pg_async_session, auth_headers, sample_user):
        """Test 404 when source doesn't exist."""
        non_existent_id = uuid.uuid4()

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.get(
            f"/api/v1/sources/{non_existent_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateSourceEndpoint:
    """Tests for PUT /sources/{source_id}"""

    @pytest.mark.asyncio
    async def test_update_source_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful source update."""
        # Arrange
        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Original Name",
            url="https://original.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        update_payload = {
            "name": "Updated Name",
            "scrape_frequency": "HOURLY",
            "is_active": False,
        }

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.put(
            f"/api/v1/sources/{source.id}",
            json=update_payload,
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["source"]["name"] == "Updated Name"
        assert data["data"]["source"]["scrape_frequency"] == "HOURLY"
        assert data["data"]["source"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_source_partial(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test partial update (only some fields)."""
        # Arrange
        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Original",
            url="https://original.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        update_payload = {"is_active": False}

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.put(
            f"/api/v1/sources/{source.id}",
            json=update_payload,
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Name should remain unchanged
        assert data["data"]["source"]["name"] == "Original"
        assert data["data"]["source"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test update of non-existent source."""
        non_existent_id = uuid.uuid4()
        update_payload = {"name": "New Name"}

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.put(
            f"/api/v1/sources/{non_existent_id}",
            json=update_payload,
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteSourceEndpoint:
    """Tests for DELETE /sources/{source_id}"""

    @pytest.mark.asyncio
    async def test_delete_source_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful source deletion."""
        # Arrange
        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="To Delete",
            url="https://delete.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        source_id = source.id

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.delete(
            f"/api/v1/sources/{source_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        # Verify source is soft-deleted (default behavior)
        deleted_source = await pg_async_session.get(Source, source_id)
        assert deleted_source is not None
        assert deleted_source.is_deleted is True

    @pytest.mark.asyncio
    async def test_delete_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test deletion of non-existent source."""
        non_existent_id = uuid.uuid4()

        # Override dependencies
        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Act
        response = await client.delete(
            f"/api/v1/sources/{non_existent_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
