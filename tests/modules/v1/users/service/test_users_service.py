from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.users.service.user import UserCRUD


@pytest.mark.asyncio
async def test_create_admin_user_success():
    """Test that admin user is created successfully."""

    db = AsyncMock()

    mock_user_instance = MagicMock()
    mock_user_instance.id = uuid4()
    mock_user_instance.email = "admin@example.com"
    mock_user_instance.organization_id = uuid4()

    with patch(
        "app.api.modules.v1.users.service.user.User",
        return_value=mock_user_instance,
    ):
        result = await UserCRUD.create_admin_user(
            db=db,
            email="admin@example.com",
            name="Admin User",
            hashed_password="hashed",
            organization_id=uuid4(),
            role_id=uuid4(),
        )

    db.add.assert_called_once_with(mock_user_instance)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(mock_user_instance)

    assert result is mock_user_instance
    assert result.email == "admin@example.com"


@pytest.mark.asyncio
async def test_create_admin_user_failure():
    """Test error is raised when DB operation fails."""

    db = AsyncMock()
    db.flush.side_effect = Exception("DB error")

    with pytest.raises(Exception) as exc:
        await UserCRUD.create_admin_user(
            db=db,
            email="admin@example.com",
            name="Admin User",
            hashed_password="hashed",
            organization_id=uuid4(),
            role_id=uuid4(),
        )

    assert "Failed to create admin user" in str(exc.value)
