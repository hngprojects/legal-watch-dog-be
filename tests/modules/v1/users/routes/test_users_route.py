"""Tests for user profile routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.routes.users_route import update_user_profile
from app.api.modules.v1.users.schemas.user_profile_schema import UpdateUserProfileRequest


@pytest.mark.asyncio
async def test_update_user_profile_success():
    """Test successful user profile update."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "test@example.com"
    mock_current_user.name = "Old Name"
    mock_current_user.avatar_url = None

    payload = UpdateUserProfileRequest(name="New Name", avatar_url="https://example.com/avatar.png")

    updated_user = MagicMock(spec=User)
    updated_user.id = mock_current_user.id
    updated_user.email = mock_current_user.email
    updated_user.name = payload.name
    updated_user.avatar_url = payload.avatar_url
    updated_user.is_active = True
    updated_user.is_verified = True
    updated_user.created_at = MagicMock()
    updated_user.created_at.isoformat.return_value = "2024-01-01T00:00:00Z"
    updated_user.updated_at = MagicMock()
    updated_user.updated_at.isoformat.return_value = "2024-01-01T00:00:00Z"

    with patch(
        "app.api.modules.v1.users.routes.users_route.UserCRUD.update_user", new_callable=AsyncMock
    ) as mock_update:
        mock_update.return_value = updated_user

        response = await update_user_profile(
            payload=payload, current_user=mock_current_user, db=mock_db
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.body.decode()
        assert "Profile updated successfully" in data
        assert "New Name" in data
        assert "https://example.com/avatar.png" in data

        mock_update.assert_called_once_with(
            db=mock_db,
            user_id=mock_current_user.id,
            name="New Name",
            avatar_url="https://example.com/avatar.png",
        )


@pytest.mark.asyncio
async def test_update_user_profile_no_fields():
    """Test update with no fields provided."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    payload = UpdateUserProfileRequest(name=None, avatar_url=None)

    response = await update_user_profile(
        payload=payload, current_user=mock_current_user, db=mock_db
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No fields to update" in response.body.decode()
