import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.organization.service.organization_repository import OrganizationCRUD
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger("app")


class OrganizationService:
    """Service class for organization business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize organization service.

        Args:
            db: Async database session
        """
        self.db = db

    async def create_organization(
        self,
        user_id: uuid.UUID,
        name: str,
        industry: str | None = None,
    ) -> dict:
        """
        Create a new organization and set the user as admin.


        - Validates that the user exists and is verified
        - Validates that the user hasn't already created an organization
        - Creates the organization
        - Creates an admin role for the organization
        - Updates the user's organization_id and role_id to admin

        Args:
            user_id: UUID of the user creating the organization
            name: Organization name
            industry: Optional industry type

        Returns:
            dict: Dictionary containing organization and user details

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        cached_user_id = user_id

        logger.info(f"Starting organization creation for user_id={user_id}")

        try:
            user = await UserCRUD.get_by_id(self.db, user_id)
            if not user:
                raise ValueError("User not found")

            if not user.is_verified:
                raise ValueError("User email must be verified before creating an organization")

            existing_org = await OrganizationCRUD.get_by_name(self.db, name)
            if existing_org:
                raise ValueError("Organization with this name already exists")

            organization = await OrganizationCRUD.create_organization(
                db=self.db,
                name=name,
                industry=industry,
            )

            admin_role = await RoleCRUD.create_admin_role(
                db=self.db,
                organization_id=organization.id,
                role_name="Admin",
                description="Organization administrator with full permissions",
            )

            await UserOrganizationCRUD.add_user_to_organization(
                db=self.db,
                user_id=user_id,
                organization_id=organization.id,
                role_id=admin_role.id,
                is_active=True,
            )

            await self.db.commit()

            logger.info(
                f"Successfully created organization id={organization.id} "
                f"for user_id={user_id} with admin role"
            )

            return {
                "organization_id": str(organization.id),
                "organization_name": organization.name,
                "user_id": str(user_id),
                "role": admin_role.name,
            }

        except ValueError as e:
            logger.warning(
                f"Validation error in organization creation for user_id={cached_user_id}: {str(e)}"
            )
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in organization creation for user_id={cached_user_id}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise Exception("An error occurred while creating the organization. Please try again.")

    async def get_user_role_in_organization(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> str | None:
        """
        Get the user's role in a specific organization.

        Args:
            user_id: User UUID
            organization_id: Organization UUID

        Returns:
            Role name or None if user is not a member
        """
        membership = await UserOrganizationCRUD.get_user_organization(
            self.db, user_id, organization_id
        )

        if not membership or not membership.is_active:
            return None

        role = await self.db.get(Role, membership.role_id)
        return role.name if role else None

    async def check_user_permission(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        permission: str,
    ) -> bool:
        """
        Check if user has a specific permission in an organization.

        Args:
            user_id: User UUID
            organization_id: Organization UUID
            permission: Permission to check (e.g., "organization:write")

        Returns:
            True if user has permission, False otherwise
        """
        membership = await UserOrganizationCRUD.get_user_organization(
            self.db, user_id, organization_id
        )

        if not membership or not membership.is_active:
            return False

        from app.api.modules.v1.users.models.roles_model import Role

        role = await self.db.get(Role, membership.role_id)

        if not role:
            return False

        return role.permissions.get(permission, False)

    async def get_organization_details(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> dict:
        """
        Get organization details.

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the details

        Returns:
            dict: Dictionary containing organization details

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        logger.info(
            f"Fetching organization details for org_id={organization_id} "
            f"by user_id={requesting_user_id}"
        )

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            membership = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )

            if not membership or not membership.is_active:
                raise ValueError("You do not have access to this organization")

            role = await self.db.get(Role, membership.role_id)

            logger.info(f"Successfully retrieved organization details for org_id={organization_id}")

            return {
                "organization_id": str(organization.id),
                "name": organization.name,
                "industry": organization.industry,
                "settings": organization.settings,
                "billing_info": organization.billing_info,
                "is_active": organization.is_active,
                "created_at": organization.created_at.isoformat(),
                "updated_at": organization.updated_at.isoformat(),
                "user_role": role.name if role else None,
            }

        except ValueError as e:
            logger.warning(
                f"Validation error fetching organization org_id={organization_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching organization org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve organization details")

    async def update_organization(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        name: str | None = None,
        industry: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        """
        Update organization details.

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the update
            name: Optional new organization name
            industry: Optional new industry
            is_active: Optional new active status

        Returns:
            dict: Dictionary containing updated organization details

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        logger.info(
            f"Updating organization org_id={organization_id} by user_id={requesting_user_id}"
        )

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            has_permission = await self.check_user_permission(
                requesting_user_id, organization_id, "manage_organization"
            )

            if not has_permission:
                raise ValueError("You do not have permission to update this organization")

            if name and name != organization.name:
                existing_org = await OrganizationCRUD.get_by_name(self.db, name)
                if existing_org and existing_org.id != organization_id:
                    raise ValueError("Organization with this name already exists")

            updated_organization = await OrganizationCRUD.update(
                db=self.db,
                organization_id=organization_id,
                name=name,
                industry=industry,
                is_active=is_active,
            )

            await self.db.commit()

            membership = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )
            role = await self.db.get(Role, membership.role_id) if membership else None

            logger.info(f"Successfully updated organization org_id={organization_id}")

            return {
                "organization_id": str(updated_organization.id),
                "name": updated_organization.name,
                "industry": updated_organization.industry,
                "settings": updated_organization.settings,
                "billing_info": updated_organization.billing_info,
                "is_active": updated_organization.is_active,
                "created_at": updated_organization.created_at.isoformat(),
                "updated_at": updated_organization.updated_at.isoformat(),
                "user_role": role.name if role else None,
            }

        except ValueError as e:
            logger.warning(
                f"Validation error updating organization org_id={organization_id}: {str(e)}"
            )
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating organization org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise Exception("Failed to update organization")

    async def get_user_organizations(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        """
        Get all organizations where the user is a member (paginated).

        Args:
            user_id: User UUID
            page: Page number (default: 1)
            limit: Items per page (default: 10)

        Returns:
            dict: Dictionary with paginated organizations and metadata
        """
        skip = (page - 1) * limit

        result = await UserOrganizationCRUD.get_all_user_organizations(
            db=self.db,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )

        organizations = result["organizations"]
        total = result["total"]

        pagination = calculate_pagination(total=total, page=page, limit=limit)

        return {"organizations": organizations, **pagination}

    async def get_organization_users(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        active_only: bool = True,
    ) -> dict:
        """
        Get all users in an organization (paginated).

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the data
            page: Page number (default: 1)
            limit: Items per page (default: 10)
            active_only: Only return active memberships (default: True)

        Returns:
            dict: Dictionary with paginated users and metadata

        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Fetching users for org_id={organization_id} by user_id={requesting_user_id}")

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            membership = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )

            if not membership or not membership.is_active:
                raise ValueError("You do not have access to this organization")

            skip = (page - 1) * limit

            result = await UserOrganizationCRUD.get_all_users_in_organization(
                db=self.db,
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                active_only=active_only,
            )

            users = result["users"]
            total = result["total"]

            pagination = calculate_pagination(total=total, page=page, limit=limit)

            logger.info(f"Successfully retrieved {len(users)} users for org_id={organization_id}")

            return {"users": users, **pagination}

        except ValueError as e:
            logger.warning(
                f"Validation error fetching users for org_id={organization_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching users for org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve organization users")
