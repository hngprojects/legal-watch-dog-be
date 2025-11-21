from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.organization.service.organization import OrganizationCRUD


@pytest.mark.asyncio
async def test_create_organization_success():
    """Test successful creation of an organization."""

    # Mock DB session
    db = AsyncMock()

    # Mock Organization model instance
    mock_org_instance = MagicMock()
    mock_org_instance.id = "123"
    mock_org_instance.name = "TestOrg"
    mock_org_instance.industry = "Tech"

    with patch(
        "app.api.modules.v1.organization.service.organization.Organization",
        return_value=mock_org_instance,
    ):
        result = await OrganizationCRUD.create_organization(
            db=db,
            name="TestOrg",
            industry="Tech",
        )

    db.add.assert_called_once_with(mock_org_instance)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(mock_org_instance)

    assert result is mock_org_instance
    assert result.name == "TestOrg"
    assert result.industry == "Tech"


@pytest.mark.asyncio
async def test_create_organization_failure():
    """Test that an exception is raised when DB operations fail."""

    db = AsyncMock()
    db.flush.side_effect = Exception("DB failure")

    with pytest.raises(Exception) as exc:
        await OrganizationCRUD.create_organization(
            db=db,
            name="FailOrg",
        )

    assert "Failed to create organization" in str(exc.value)
