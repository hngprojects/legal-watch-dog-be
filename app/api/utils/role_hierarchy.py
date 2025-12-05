import logging
from enum import IntEnum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.role_exceptions import CannotAssignRoleException, CannotManageHigherRoleException
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.models.roles_model import Role

logger = logging.getLogger("app")


class RoleLevel(IntEnum):
    """
    Role hierarchy levels (higher number = higher authority).
    """

    MEMBER = 1
    MANAGER = 2
    ADMIN = 3
    OWNER = 4


class RoleHierarchy:
    """Manages role hierarchy and permissions."""

    ROLE_LEVELS = {
        "Member": RoleLevel.MEMBER,
        "Manager": RoleLevel.MANAGER,
        "Admin": RoleLevel.ADMIN,
        "Owner": RoleLevel.OWNER,
    }

    @classmethod
    def get_role_level(cls, role_name: str) -> int:
        """
        Get the hierarchy level of a role.

        Args:
            role_name: Name of the role

        Returns:
            int: Hierarchy level (higher = more authority)
        """
        return cls.ROLE_LEVELS.get(role_name, RoleLevel.MEMBER)

    @staticmethod
    def can_manage_role(user_hierarchy_level: int, target_hierarchy_level: int) -> bool:
        """
        Check if user can manage target based on hierarchy levels.

        Rules:
        - Can only manage roles at lower levels
        - Cannot manage roles at same or higher level

        Args:
            user_hierarchy_level: Hierarchy level of user performing action
            target_hierarchy_level: Hierarchy level of user being managed

        Returns:
            bool: True if user can manage target
        """
        return user_hierarchy_level > target_hierarchy_level

    @classmethod
    @classmethod
    def can_assign_role_by_level(cls, user_level: int, target_level: int) -> bool:
        """
        Check if user can assign target role by hierarchy levels.

        Args:
            user_level: User's hierarchy level (1-4)
            target_level: Target role hierarchy level (1-4)

        Returns:
            bool: True if user can assign target role
        """
        if user_level == RoleLevel.OWNER:
            return True

        return user_level > target_level


async def validate_role_hierarchy(
    db: AsyncSession,
    current_user_id: str,
    target_user_id: str,
    organization_id: str,
    action: str,
    new_role_name: Optional[str] = None,
) -> tuple[bool, str, Role, Role]:
    """
    Validate if an user can perform an action on a target user based on role hierarchy.

    Args:
        db: Database session
        current_user_id: UUID of the user performing the action
        target_user_id: UUID of the user being acted upon
        organization_id: UUID of the organization
        action: Action being performed ('manage', 'assign_role', 'deactivate', 'delete')
        new_role_name: Optional new role name (required for 'assign_role' action)

    Returns:
        tuple: (is_valid, error_message, user_role, target_role)

    Raises:
        - MembershipNotFoundException: If memberships are not found
        - RoleNotFoundException: If roles are not found
        - CannotManageHigherRoleException: If trying to manage equal/higher role
        - CannotAssignRoleException: If trying to assign a role above your level
    """

    user_membership = await UserOrganizationCRUD.get_user_organization(
        db, current_user_id, organization_id
    )
    if not user_membership:
        raise ValueError("You are not a member of this organization")

    user_role = await db.get(Role, user_membership.role_id)
    if not user_role:
        raise ValueError("Your role could not be found")

    target_membership = await UserOrganizationCRUD.get_user_organization(
        db, target_user_id, organization_id
    )
    if not target_membership:
        raise ValueError("Target user is not a member of this organization")

    target_role = await db.get(Role, target_membership.role_id)
    if not target_role:
        raise ValueError("Target user's role could not be found")

    if action == "assign_role":
        if not new_role_name:
            raise ValueError("New role name is required for 'assign_role'")

        stmt = select(Role).where(
            Role.name == new_role_name,
            Role.organization_id == organization_id,
        )
        result = await db.execute(stmt)
        new_role = result.scalar_one_or_none()

        if not new_role:
            raise ValueError(f"Role '{new_role_name}' not found in this organization")

        if not RoleHierarchy.can_manage_role(user_role.name, target_role.name):
            raise CannotManageHigherRoleException(
                user_role=user_role.name, target_role=target_role.name, action="modify"
            )

        if not RoleHierarchy.can_assign_role(user_role.name, new_role_name):
            raise CannotAssignRoleException(
                user_role=user_role.name, target_role_name=new_role_name
            )

    elif action in ["manage", "deactivate", "delete"]:
        if not RoleHierarchy.can_manage_role(user_role.name, target_role.name):
            action_verb = {
                "manage": "manage",
                "deactivate": "deactivate",
                "delete": "remove",
            }.get(action, "manage")

            raise CannotManageHigherRoleException(
                user_role=user_role.name, target_role=target_role.name, action=action_verb
            )

    else:
        raise ValueError(f"Unknown action: {action}")

    return True, "", user_role, target_role


async def get_user_role_name(
    db: AsyncSession,
    user_id: str,
    organization_id: str,
) -> Optional[str]:
    """
    Get the role name of a user in an organization.

    Args:
        db: Database session
        user_id: UUID of the user
        organization_id: UUID of the organization

    Returns:
        Optional[str]: Role name or None if not found
    """
    membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)
    if not membership:
        return None

    role = await db.get(Role, membership.role_id)
    return role.name if role else None


# Add this method to the RoleHierarchy class in role_hierarchy.py:


@staticmethod
async def get_role_by_name(
    db: AsyncSession,
    role_name: str,
    organization_id: str,
) -> Optional[Role]:
    """
    Get a role by name and organization.

    Args:
        db: Database session
        role_name: Name of the role
        organization_id: UUID of the organization

    Returns:
        Role object or None if not found
    """
    from sqlalchemy import select

    from app.api.modules.v1.users.models.roles_model import Role

    try:
        stmt = select(Role).where(
            Role.name == role_name,
            Role.organization_id == organization_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting role by name '{role_name}': {str(e)}")
        return None
