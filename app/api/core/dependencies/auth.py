import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.redis_service import is_token_denylisted
from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import decode_token
from app.api.utils.permissions import Permission

setup_logging()
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
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
            )

        if not user.is_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

        logger.info(f"Authenticated user: {user.email}")
        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
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
