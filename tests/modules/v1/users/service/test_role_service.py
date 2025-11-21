from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.users.service.role import RoleCRUD


@pytest.mark.asyncio
async def test_create_admin_role_success():
    """Test successful creation of admin role."""

    db = AsyncMock()

    mock_role_instance = MagicMock()
    mock_role_instance.id = uuid4()
    mock_role_instance.name = "Admin"
    mock_role_instance.organization_id = uuid4()

    with patch(
        "app.api.modules.v1.users.service.role.Role",
        return_value=mock_role_instance,
    ):
        result = await RoleCRUD.create_admin_role(
            db=db,
            organization_id=uuid4(),
        )

    db.add.assert_called_once_with(mock_role_instance)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(mock_role_instance)

    assert result is mock_role_instance
    assert result.name == "Admin"


@pytest.mark.asyncio
async def test_create_admin_role_failure():
    """Test that an exception is raised when DB operations fail."""

    db = AsyncMock()
    db.flush.side_effect = Exception("DB crash")

    with pytest.raises(Exception) as exc:
        await RoleCRUD.create_admin_role(
            db=db,
            organization_id=uuid4(),
        )

    assert "Failed to create admin role" in str(exc.value)
