"""
Unit tests for SourceService.

Tests all CRUD operations and business logic for source management.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

mock_fernet = MagicMock()
mock_fernet.encrypt.return_value.decode.return_value = "mock_encrypted_value"
with patch("cryptography.fernet.Fernet", return_value=mock_fernet):
    from app.api.modules.v1.scraping.models.source_model import Source, SourceType
    from app.api.modules.v1.scraping.schemas.source_service import (
        SourceCreate,
        SourceRead,
        SourceUpdate,
    )
    from app.api.modules.v1.scraping.service.source_service import SourceService


@pytest.fixture
def sample_jurisdiction_id():
    """Fixture for a sample jurisdiction UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_source_create(sample_jurisdiction_id):
    """Fixture for SourceCreate schema."""
    return SourceCreate(
        jurisdiction_id=sample_jurisdiction_id,
        name="Test Ministry Website",
        url="https://example.gov/laws",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
        auth_details={"username": "testuser", "password": "testpass"},
        scraping_rules={"selector": ".law-content"},
    )


@pytest.fixture
def sample_source_db(sample_jurisdiction_id):
    """Fixture for Source database model."""
    return Source(
        id=uuid.uuid4(),
        jurisdiction_id=sample_jurisdiction_id,
        name="Test Ministry Website",
        url="https://example.gov/laws",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
        is_active=True,
        auth_details_encrypted="encrypted_string_here",
        scraping_rules={"selector": ".law-content"},
    )


class TestSourceServiceCreate:
    """Tests for SourceService.create_source()"""

    @pytest.mark.asyncio
    async def test_create_source_success_with_auth(
        self, sample_source_create, sample_jurisdiction_id
    ):
        """Test successful source creation with auth details."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        created_source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name=sample_source_create.name,
            url=str(sample_source_create.url),
            source_type=sample_source_create.source_type,
            scrape_frequency=sample_source_create.scrape_frequency,
            scraping_rules=sample_source_create.scraping_rules,
            auth_details_encrypted="mock_encrypted_value",
            is_active=True,
        )

        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, "id", created_source.id))

        result = await service.create_source(mock_db, sample_source_create)
        assert isinstance(result, SourceRead)
        assert result.name == sample_source_create.name
        assert result.has_auth is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_source_success_without_auth(self, sample_jurisdiction_id):
        """Test successful source creation without auth details."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        source_data = SourceCreate(
            jurisdiction_id=sample_jurisdiction_id,
            name="Public Website",
            url="https://public.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="HOURLY",
            auth_details=None,
        )

        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.create_source(mock_db, source_data)

        assert isinstance(result, SourceRead)
        assert result.has_auth is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_source_database_error(self, sample_source_create):
        """Test that database errors are handled properly."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.status_code == 500
        assert "Failed to create source" in exc_info.value.detail
        mock_db.rollback.assert_awaited_once()


class TestSourceServiceGet:
    """Tests for SourceService.get_source()"""

    @pytest.mark.asyncio
    async def test_get_source_success(self, sample_source_db):
        """Test successful retrieval of a source."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=sample_source_db)

        result = await service.get_source(mock_db, sample_source_db.id)

        assert isinstance(result, SourceRead)
        assert result.id == sample_source_db.id
        assert result.name == sample_source_db.name
        assert result.has_auth is True
        mock_db.get.assert_awaited_once_with(Source, sample_source_db.id)

    @pytest.mark.asyncio
    async def test_get_source_not_found(self):
        """Test that 404 is raised when source doesn't exist."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()
        source_id = uuid.uuid4()

        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_source(mock_db, source_id)

        assert exc_info.value.status_code == 404
        assert "Source not found" in exc_info.value.detail


class TestSourceServiceGetSources:
    """Tests for SourceService.get_sources()"""

    @pytest.mark.asyncio
    async def test_get_sources_success(self, sample_jurisdiction_id):
        """Test successful retrieval of multiple sources."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        source1 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 1",
            url="https://example1.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
            is_active=True,
            auth_details_encrypted=None,
            scraping_rules={},
        )

        source2 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 2",
            url="https://example2.com",
            source_type=SourceType.PDF,
            scrape_frequency="WEEKLY",
            is_active=True,
            auth_details_encrypted="encrypted",
            scraping_rules={},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [source1, source2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_sources(mock_db)

        assert len(result) == 2
        assert all(isinstance(s, SourceRead) for s in result)
        assert result[0].name == "Source 1"
        assert result[1].has_auth is True

    @pytest.mark.asyncio
    async def test_get_sources_with_filters(self, sample_jurisdiction_id):
        """Test get_sources with jurisdiction filter."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_sources(
            mock_db,
            jurisdiction_id=sample_jurisdiction_id,
            is_active=True,
            skip=10,
            limit=50,
        )

        assert isinstance(result, list)
        mock_db.execute.assert_awaited_once()


class TestSourceServiceUpdate:
    """Tests for SourceService.update_source()"""

    @pytest.mark.asyncio
    async def test_update_source_success(self, sample_source_db):
        """Test successful source update."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        update_data = SourceUpdate(
            name="Updated Name",
            scrape_frequency="HOURLY",
            is_active=False,
        )

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.update_source(mock_db, sample_source_db.id, update_data)

        assert isinstance(result, SourceRead)
        assert sample_source_db.name == "Updated Name"
        assert sample_source_db.scrape_frequency == "HOURLY"
        assert sample_source_db.is_active is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_source_with_new_auth(self, sample_source_db):
        """Test updating source with new auth details."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        update_data = SourceUpdate(auth_details={"new_user": "newpass"})

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await service.update_source(mock_db, sample_source_db.id, update_data)

        assert sample_source_db.auth_details_encrypted == "mock_encrypted_value"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_source_not_found(self):
        """Test update when source doesn't exist."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()
        source_id = uuid.uuid4()

        update_data = SourceUpdate(name="New Name")
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_source(mock_db, source_id, update_data)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_source_database_error(self, sample_source_db):
        """Test that database errors during update are handled."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        update_data = SourceUpdate(name="New Name")
        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock(side_effect=Exception("DB Error"))
        mock_db.rollback = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await service.update_source(mock_db, sample_source_db.id, update_data)

        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_awaited_once()


class TestSourceServiceDelete:
    """Tests for SourceService.delete_source()"""

    @pytest.mark.asyncio
    async def test_delete_source_success(self, sample_source_db):
        """Test successful source deletion (soft delete by default)."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.delete_source(mock_db, sample_source_db.id)

        assert "message" in result
        assert "Source successfully deleted" in result["message"]
        assert result["source_id"] == str(sample_source_db.id)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_source_not_found(self):
        """Test delete when source doesn't exist."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()
        source_id = uuid.uuid4()

        mock_db.get = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_source(mock_db, source_id)

        assert exc_info.value.status_code == 404
        assert "Source not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_source_database_error(self, sample_source_db):
        """Test that database errors during deletion are handled."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock(side_effect=Exception("DB Error"))
        mock_db.rollback = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_source(mock_db, sample_source_db.id)

        assert exc_info.value.status_code == 500
        assert "Failed to delete source" in exc_info.value.detail
        mock_db.rollback.assert_awaited_once()
