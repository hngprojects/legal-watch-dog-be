import logging
<<<<<<< HEAD
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
=======

import jwt
from fastapi import Depends, HTTPException, status
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.redis_service import is_token_denylisted
from app.api.db.database import get_db
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import decode_token
from app.api.utils.permissions import Permission

logger = logging.getLogger("app")

# HTTP Bearer token extraction
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate JWT token, return authenticated user.
    Enforces:
    - Valid JWT signature
    - Token not expired
    - Token not in denylist (logged out)
    - User exists and is active

    Raises:
        HTTPException: 401 if authentication fails
    """
    token = credentials.credentials

    try:
        # Decode and validate token
        payload = decode_token(token)

        user_id = payload.get("sub")
        jti = payload.get("jti")

        if not user_id or not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # Check if token is denylisted (logged out)
        if await is_token_denylisted(jti):
            logger.warning(f"Attempted use of denylisted token: {jti}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

        # Fetch user from database
        user = await db.scalar(select(User).where(User.id == user_id))

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
            )

        if not user.is_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

        logger.info(f"Authenticated user: {user.email}")
        return user

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


async def get_current_user_with_role(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> tuple[User, Role]:
    """
    Get current user with their role loaded.

    Returns:
        Tuple of (User, Role)
    """
    role = await db.scalar(select(Role).where(Role.id == current_user.role_id))

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role not found",
        )

    return current_user, role


def require_permission(permission: Permission):
    """
    Dependency factory for checking specific permissions.

    Usage:
        @app.get("/projects",
        dependencies=[Depends(require_permission(Permission.VIEW_PROJECTS))])

    Args:
        permission: Permission enum value required

    Returns:
        FastAPI dependency function
    """

    async def permission_checker(
        user_role: tuple[User, Role] = Depends(get_current_user_with_role),
    ) -> User:
        user, role = user_role

        # Check if user's role has the required permission
        if not role.permissions.get(permission.value, False):
            logger.warning(f"Permission denied: {user.email} lacks {permission.value}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}",
            )

        logger.info(f"Permission granted: {user.email} has {permission.value}")
        return user

    return permission_checker


def require_any_permission(*permissions: Permission):
    """
    Require at least one of the specified permissions.

    Usage:
        @app.get("/data", dependencies=[Depends(require_any_permission(
            Permission.VIEW_PROJECTS, Permission.EDIT_PROJECTS
        ))])

    Args:
        permissions: Variable number of Permission enum values

    Returns:
        FastAPI dependency function
    """

    async def permission_checker(
        user_role: tuple[User, Role] = Depends(get_current_user_with_role),
    ) -> User:
        user, role = user_role

        # Check if user has ANY of the required permissions
        has_permission = any(role.permissions.get(perm.value, False) for perm in permissions)

        if not has_permission:
            perm_names = [p.value for p in permissions]
            logger.warning(f"Permission denied: {user.email} lacks any of {perm_names}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {perm_names}",
            )

        return user

    return permission_checker


<<<<<<< HEAD
async def get_current_user_with_org_role(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Role]:
    """
    Resolve the current user’s membership and role for the organization
    identified in the request path.

    This expects routes to be nested under:
        /organizations/{organization_id}/...

    Args:
        request: Incoming FastAPI request (used to read organization_id from path).
        current_user: Authenticated user from `get_current_user`.
        db: Async SQLAlchemy session.

    Raises:
        HTTPException: 400 if organization_id is missing or invalid.
        HTTPException: 403 if the user is not a member of the organization.
        HTTPException: 500 if the membership has no associated role.

    Returns:
        Tuple[User, Role]: The authenticated user and their role within
        the organization from the URL.
    """
    organization_id_str = request.path_params.get("organization_id")
    if not organization_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context not found in path",
        )

    try:
        organization_id = UUID(organization_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization id in path",
        )

    membership = await db.scalar(
        select(UserOrganization)
        .where(UserOrganization.user_id == current_user.id)
        .where(UserOrganization.organization_id == organization_id)
        .where(UserOrganization.is_active)
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not a member of this organization",
        )

    role = await db.scalar(select(Role).where(Role.id == membership.role_id))
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role not found for membership",
        )

    return current_user, role


async def require_billing_admin(
    user_role: tuple[User, Role] = Depends(get_current_user_with_org_role),
) -> User:
    """
    Ensure the current user has billing admin permission within the
    organization from the request path.

    Args:
        user_role: Tuple of (User, Role) injected from
            `get_current_user_with_org_role`.

    Raises:
        HTTPException: 403 if the user does not have MANAGE_BILLING permission
        for the organization.

    Returns:
        User: The authenticated user, guaranteed to be allowed to manage
        billing for the current organization.
    """
    user, role = user_role

    if not role.permissions.get(Permission.MANAGE_BILLING.value, False):
        logger.warning(
            "Permission denied: %s lacks %s",
            user.email,
            Permission.MANAGE_BILLING.value,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to manage billing for this organisation.",
        )

    logger.info(
        "Permission granted: %s has %s",
        user.email,
        Permission.MANAGE_BILLING.value,
    )
    return user


=======
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
async def verify_organization_access(
    resource_org_id: str, current_user: User = Depends(get_current_user)
) -> bool:
    """
    Verify that current user's organization matches resource's organization.
    Prevents cross-tenant data access.

    Args:
        resource_org_id: Organization ID of the resource being accessed
        current_user: Current authenticated user

    Raises:
        HTTPException: 403 if organization mismatch

    Returns:
        True if access allowed
    """
    if str(current_user.organization_id) != str(resource_org_id):
        logger.warning(
            f"Organization access denied: user {current_user.email} "
            f"(org {current_user.organization_id}) attempted to access "
            f"resource from org {resource_org_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource belongs to different organization",
        )

    return True


class OrganizationFilter:
    """
    Dependency class for automatically filtering queries by organization.

    Usage:
        @app.get("/projects")
        async def get_projects(
            org_filter: OrganizationFilter = Depends(),
            db: AsyncSession = Depends(get_db)
        ):
            projects = await db.scalars(
                select(Project).where(Project.organization_id == org_filter.org_id)
            )
    """

    def __init__(self, current_user: User = Depends(get_current_user)):
        self.org_id = current_user.organization_id
        self.user = current_user


class TenantGuard:
    """
    Enforces multi-tenant isolation automatically.

    Provides:
      - current_user
      - org_id for query filtering
      - verify(resource_org_id) for checking access to a specific resource

    Router-Level Use Case:
        Protects all routes in a router from users without an organization.

    Example:
        from fastapi import APIRouter, Depends

        router = APIRouter(
            prefix="/jurisdiction",
            tags=["Jurisdictions"],
            dependencies=[Depends(TenantGuard)]  # Applied at router level
        )

        @router.get("/")
        async def list_jurisdictions():
            # All users hitting this route are guaranteed to belong to an organization
            return await get_all_jurisdictions()
    """

    def __init__(
        self, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
    ):
        self.db = db
        self.user = current_user

    async def get_membership(self, organization_id: str):
        result = await self.db.execute(
            select(UserOrganization)
            .where(UserOrganization.user_id == self.user.id)
            .where(UserOrganization.organization_id == organization_id)
        )
        membership = result.scalars().first()
        if not membership:
            raise HTTPException(status_code=403, detail="User not a member of this organization")
        return membership

    def verify(self, resource_org_id):
        """
        Validate that a resource belongs to the current user's organization.

        This method enforces multi-tenant isolation at the resource level. Call it
        inside routes or service methods to prevent users from accessing resources
        that belong to another organization.

        Args:
            resource_org_id (str | UUID): The organization ID associated with the resource.

        Raises:
            HTTPException (403): If the resource's organization ID does not match
            the current user's organization ID.

        Example:
            tenant = TenantGuard(current_user)
            tenant.verify(project.org_id)
        """
        if str(resource_org_id) != str(self.org_id):
            raise HTTPException(
                status_code=403, detail="Access denied: resource belongs to another organization"
            )
