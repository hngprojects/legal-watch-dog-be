import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.organization.service.organization_service import OrganizationService
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(prefix="/users", tags=["Users"])

logger = logging.getLogger(__name__)


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current authenticated user's complete profile.

    Returns comprehensive information about the authenticated user including:
    - Basic user information (id, email, name, etc.)
    - All organization memberships with roles
    - Account status and verification details
    - Timestamps

    Requirements:
    - User must be authenticated

    Args:
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with complete user profile

    Raises:
        HTTPException: 500 for server errors
    """
    try:
        result = await UserCRUD.get_user_profile(db=db, user_id=current_user.id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="User profile retrieved successfully",
            data=result,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch profile for user_id={current_user.id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve user profile",
        )


@router.get(
    "/{user_id}/organisations",
    status_code=status.HTTP_200_OK,
)
async def get_user_organizations(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all organizations a user is a member of.

    Returns all organizations where the user has an active membership,
    along with their role in each organization.

    Requirements:
    - User must be authenticated
    - User can only view their own organizations (user_id must match current_user.id)

    Args:
        user_id: UUID of the user
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with list of organizations

    Raises:
        HTTPException: 403 for forbidden, 500 for server errors
    """
    try:
        if user_id != current_user.id:
            return error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                message="You can only view your own organizations",
            )

        service = OrganizationService(db)
        result = await service.get_user_organizations(
            user_id=user_id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organizations retrieved successfully",
            data=result,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch organizations for user_id={user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organizations",
        )


@router.get(
    "/{user_id}/organisations/{organization_id}",
    status_code=status.HTTP_200_OK,
)
async def get_user_organization_details(
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of the organization.

    Returns detailed information about an organization where the user
    is a member, including their role and the organization's details.

    Requirements:
    - User must be authenticated
    - User can only view their own organization details (user_id must match current_user.id)
    - User must be a member of the organization

    Args:
        user_id: UUID of the user
        organization_id: UUID of the organization
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with organization details

    Raises:
        HTTPException: 403 for forbidden, 404 for not found, 500 for server errors
    """
    try:
        if user_id != current_user.id:
            return error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                message="You can only view your own organization details",
            )

        service = OrganizationService(db)
        result = await service.get_organization_details(
            organization_id=organization_id,
            requesting_user_id=user_id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization details retrieved successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to get org details for user_id={user_id}, org_id={organization_id}: {str(e)}"
        )
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "do not have access" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Failed to get org details for user_id={user_id}, org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organization details. Please try again later.",
        )
