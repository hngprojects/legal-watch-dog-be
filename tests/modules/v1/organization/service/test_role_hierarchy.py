import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.role_exceptions import (
    CannotAssignRoleException,
    CannotManageHigherRoleException,
)
from app.api.utils.role_hierarchy import RoleHierarchy, RoleLevel, validate_role_hierarchy


class TestRoleHierarchyGetLevel:
    """Test RoleHierarchy.get_role_level() method."""

    def test_get_owner_level(self):
        """Test that Owner role returns correct level."""
        assert RoleHierarchy.get_role_level("Owner") == RoleLevel.OWNER
        assert RoleHierarchy.get_role_level("Owner") == 4

    def test_get_admin_level(self):
        """Test that Admin role returns correct level."""
        assert RoleHierarchy.get_role_level("Admin") == RoleLevel.ADMIN
        assert RoleHierarchy.get_role_level("Admin") == 3

    def test_get_manager_level(self):
        """Test that Manager role returns correct level."""
        assert RoleHierarchy.get_role_level("Manager") == RoleLevel.MANAGER
        assert RoleHierarchy.get_role_level("Manager") == 2

    def test_get_member_level(self):
        """Test that Member role returns correct level."""
        assert RoleHierarchy.get_role_level("Member") == RoleLevel.MEMBER
        assert RoleHierarchy.get_role_level("Member") == 1

    def test_get_unknown_role_defaults_to_member(self):
        """Test that unknown roles default to Member level."""
        assert RoleHierarchy.get_role_level("UnknownRole") == RoleLevel.MEMBER
        assert RoleHierarchy.get_role_level("CustomRole") == 1


class TestRoleHierarchyCanManage:
    """Test RoleHierarchy.can_manage_role() method."""

    def test_owner_can_manage_admin(self):
        """Test that Owner can manage Admin."""
        assert RoleHierarchy.can_manage_role("Owner", "Admin") is True

    def test_owner_can_manage_manager(self):
        """Test that Owner can manage Manager."""
        assert RoleHierarchy.can_manage_role("Owner", "Manager") is True

    def test_owner_can_manage_member(self):
        """Test that Owner can manage Member."""
        assert RoleHierarchy.can_manage_role("Owner", "Member") is True

    def test_owner_cannot_manage_owner(self):
        """Test that Owner cannot manage another Owner."""
        assert RoleHierarchy.can_manage_role("Owner", "Owner") is False

    def test_admin_can_manage_manager(self):
        """Test that Admin can manage Manager."""
        assert RoleHierarchy.can_manage_role("Admin", "Manager") is True

    def test_admin_can_manage_member(self):
        """Test that Admin can manage Member."""
        assert RoleHierarchy.can_manage_role("Admin", "Member") is True

    def test_admin_cannot_manage_admin(self):
        """Test that Admin cannot manage another Admin."""
        assert RoleHierarchy.can_manage_role("Admin", "Admin") is False

    def test_admin_cannot_manage_owner(self):
        """Test that Admin cannot manage Owner."""
        assert RoleHierarchy.can_manage_role("Admin", "Owner") is False

    def test_manager_can_manage_member(self):
        """Test that Manager can manage Member."""
        assert RoleHierarchy.can_manage_role("Manager", "Member") is True

    def test_manager_cannot_manage_manager(self):
        """Test that Manager cannot manage another Manager."""
        assert RoleHierarchy.can_manage_role("Manager", "Manager") is False

    def test_manager_cannot_manage_admin(self):
        """Test that Manager cannot manage Admin."""
        assert RoleHierarchy.can_manage_role("Manager", "Admin") is False

    def test_manager_cannot_manage_owner(self):
        """Test that Manager cannot manage Owner."""
        assert RoleHierarchy.can_manage_role("Manager", "Owner") is False

    def test_member_cannot_manage_anyone(self):
        """Test that Member cannot manage any role."""
        assert RoleHierarchy.can_manage_role("Member", "Member") is False
        assert RoleHierarchy.can_manage_role("Member", "Manager") is False
        assert RoleHierarchy.can_manage_role("Member", "Admin") is False
        assert RoleHierarchy.can_manage_role("Member", "Owner") is False


class TestRoleHierarchyCanAssign:
    """Test RoleHierarchy.can_assign_role() method."""

    def test_owner_can_assign_owner(self):
        """Test that Owner can assign Owner role."""
        assert RoleHierarchy.can_assign_role("Owner", "Owner") is True

    def test_owner_can_assign_admin(self):
        """Test that Owner can assign Admin role."""
        assert RoleHierarchy.can_assign_role("Owner", "Admin") is True

    def test_owner_can_assign_manager(self):
        """Test that Owner can assign Manager role."""
        assert RoleHierarchy.can_assign_role("Owner", "Manager") is True

    def test_owner_can_assign_member(self):
        """Test that Owner can assign Member role."""
        assert RoleHierarchy.can_assign_role("Owner", "Member") is True

    def test_admin_cannot_assign_owner(self):
        """Test that Admin CANNOT assign Owner role."""
        assert RoleHierarchy.can_assign_role("Admin", "Owner") is False

    def test_admin_can_assign_admin(self):
        """Test that Admin can assign Admin role."""
        assert (
            RoleHierarchy.can_assign_role("Admin", "Admin") is False
        )  # Changed: Admin can only assign below

    def test_admin_can_assign_manager(self):
        """Test that Admin can assign Manager role."""
        assert RoleHierarchy.can_assign_role("Admin", "Manager") is True

    def test_admin_can_assign_member(self):
        """Test that Admin can assign Member role."""
        assert RoleHierarchy.can_assign_role("Admin", "Member") is True

    def test_manager_cannot_assign_owner(self):
        """Test that Manager cannot assign Owner role."""
        assert RoleHierarchy.can_assign_role("Manager", "Owner") is False

    def test_manager_cannot_assign_admin(self):
        """Test that Manager cannot assign Admin role."""
        assert RoleHierarchy.can_assign_role("Manager", "Admin") is False

    def test_manager_can_assign_manager(self):
        """Test that Manager can assign Manager role."""
        assert RoleHierarchy.can_assign_role("Manager", "Manager") is False

    def test_manager_can_assign_member(self):
        """Test that Manager can assign Member role."""
        assert RoleHierarchy.can_assign_role("Manager", "Member") is True

    def test_member_cannot_assign_any_role(self):
        """Test that Member cannot assign any role."""
        assert RoleHierarchy.can_assign_role("Member", "Owner") is False
        assert RoleHierarchy.can_assign_role("Member", "Admin") is False
        assert RoleHierarchy.can_assign_role("Member", "Manager") is False
        assert RoleHierarchy.can_assign_role("Member", "Member") is False


@pytest.mark.asyncio
class TestValidateRoleHierarchy:
    """Test validate_role_hierarchy() function."""

    async def test_owner_can_assign_owner_role(self):
        """Test that Owner can assign Owner role to another user."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Owner"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.utils.role_hierarchy.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            result = await validate_role_hierarchy(
                db=db,
                current_user_id=str(uuid.uuid4()),
                target_user_id=str(uuid.uuid4()),
                organization_id=str(uuid.uuid4()),
                action="assign_role",
                new_role_name="Owner",
            )

            assert result[0] is True
            assert result[1] == ""

    async def test_admin_cannot_assign_owner_role(self):
        """Test that Admin CANNOT assign Owner role."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.utils.role_hierarchy.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(CannotAssignRoleException) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="assign_role",
                    new_role_name="Owner",
                )

            assert "cannot assign the Owner role" in str(exc.value)

    async def test_admin_can_assign_manager_role(self):
        """Test that Admin can assign Manager role."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.utils.role_hierarchy.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            result = await validate_role_hierarchy(
                db=db,
                current_user_id=str(uuid.uuid4()),
                target_user_id=str(uuid.uuid4()),
                organization_id=str(uuid.uuid4()),
                action="assign_role",
                new_role_name="Manager",
            )

            assert result[0] is True

    async def test_manager_cannot_assign_admin_role(self):
        """Test that Manager cannot assign Admin role."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Manager"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.utils.role_hierarchy.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(CannotAssignRoleException) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="assign_role",
                    new_role_name="Admin",
                )

            assert "cannot assign the Admin role" in str(exc.value)

    async def test_admin_cannot_manage_owner(self):
        """Test that Admin cannot manage Owner."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Owner"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.utils.role_hierarchy.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(CannotManageHigherRoleException) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="deactivate",
                )

            assert "cannot deactivate a Owner" in str(exc.value)

    async def test_owner_can_manage_admin(self):
        """Test that Owner can manage Admin."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Owner"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Admin"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.utils.role_hierarchy.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            result = await validate_role_hierarchy(
                db=db,
                current_user_id=str(uuid.uuid4()),
                target_user_id=str(uuid.uuid4()),
                organization_id=str(uuid.uuid4()),
                action="delete",
            )

            assert result[0] is True

    async def test_missing_new_role_name_for_assign_action(self):
        """Test that assign_role action requires new_role_name."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.modules.v1.organization.service.user_organization_service.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(ValueError) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="assign_role",
                    new_role_name=None,
                )

            assert "New role name is required" in str(exc.value)

    async def test_user_not_member_of_organization(self):
        """Test that ValueError is raised when user is not a member."""
        db = AsyncMock()

        with patch(
            "app.api.modules.v1.organization.service.user_organization_service.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.return_value = None

            with pytest.raises(ValueError) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="manage",
                )

            assert "not a member of this organization" in str(exc.value)

    async def test_invalid_action(self):
        """Test that ValueError is raised for unknown action."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.modules.v1.organization.service.user_organization_service.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(ValueError) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="unknown_action",
                )

            assert "Unknown action" in str(exc.value)
