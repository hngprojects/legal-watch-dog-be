from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.users.service.role import RoleCRUD, RoleTemplateCRUD


@pytest.mark.asyncio
async def test_create_admin_role_success():
    """Test successful creation of admin role."""

    db = AsyncMock()
    org_id = uuid4()

    # Mock template
    mock_template = MagicMock()
    mock_template.name = "admin"
    mock_template.display_name = "Admin"
    mock_template.description = "Administrator with full permissions"
    mock_template.permissions = {"manage_users": True, "invite_users": True}
    mock_template.hierarchy_level = 3

    # Mock role instance
    mock_role_instance = MagicMock()
    mock_role_instance.id = uuid4()
    mock_role_instance.name = "Admin"
    mock_role_instance.organization_id = org_id
    mock_role_instance.permissions = {"manage_users": True, "invite_users": True}
    mock_role_instance.hierarchy_level = 3
    mock_role_instance.template_name = "admin"
    mock_role_instance.description = "Administrator with full permissions"

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
    org_id = uuid4()

    # Mock template
    mock_template = MagicMock()
    mock_template.name = "admin"
    mock_template.display_name = "Admin"
    mock_template.description = "Administrator with full permissions"
    mock_template.permissions = {"manage_users": True, "invite_users": True}
    mock_template.hierarchy_level = 3

    # Mock Role constructor
    mock_role_instance = MagicMock()
    with patch.object(RoleTemplateCRUD, "get_template_by_name", return_value=mock_template):
        with patch("app.api.modules.v1.users.service.role.Role", return_value=mock_role_instance):
            # Make flush fail
            db.flush.side_effect = Exception("DB crash")

            with pytest.raises(Exception) as exc:
                await RoleCRUD.create_admin_role(
                    db=db,
                    organization_id=org_id,
                )

    # Check the error message matches what your code actually raises
    assert "Failed to create role from template 'admin'" in str(exc.value)
