import logging
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.organization.routes.docs.organization_route_docs import (
    get_organization_custom_errors,
    get_organization_custom_success,
    get_organization_responses,
)
from app.api.modules.v1.organization.schemas.invitation_schema import InvitationResponse
from app.api.modules.v1.organization.schemas.organization_schema import (
    OrganizationDetailResponse,
)
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
from app.api.modules.v1.organization.service.organization_service import OrganizationService
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.routes.docs.user_routes_docs import (
    get_user_organizations_custom_errors,
    get_user_organizations_custom_success,
    get_user_organizations_responses,
    get_user_profile_custom_errors,
    get_user_profile_custom_success,
    get_user_profile_responses,
)
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(prefix="/users", tags=["Users"])

logger = logging.getLogger("app")


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    responses=get_user_profile_responses,
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


get_current_user_profile._custom_errors = get_user_profile_custom_errors
get_current_user_profile._custom_success = get_user_profile_custom_success


@router.get(
    "/me/invitations",
    response_model=list[InvitationResponse],
    status_code=status.HTTP_200_OK,
)
async def get_my_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all pending invitations for the current authenticated user.

    Returns a list of all pending organization invitations that the current user has received.

    Requirements:
    - User must be authenticated

    Args:
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        List[InvitationResponse]: Success response with list of pending invitations

    Raises:
        HTTPException: 500 for server errors
    """
    try:
        invitations = await InvitationCRUD.get_pending_invitations_for_user_email(
            db, current_user.email
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Pending invitations retrieved successfully",
            data=invitations,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch pending invitations for user_id={current_user.id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve pending invitations",
        )


@router.get(
    "/me/organizations",
    status_code=status.HTTP_200_OK,
    responses=get_user_organizations_responses,
)
async def get_all_user_organizations(
    page: int = Query(default=1, ge=1, description="Page number (minimum: 1)"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
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
    user_id = current_user.id
    try:
        service = OrganizationService(db)
        result = await service.get_user_organizations(
            user_id=user_id,
            page=page,
            limit=limit,
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


get_all_user_organizations._custom_errors = get_user_organizations_custom_errors
get_all_user_organizations._custom_success = get_user_organizations_custom_success


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
    

@router.get(
    "/me/organizations/{organization_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
    responses=get_organization_responses,
)
async def get_organization_details(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get organization details.

    This endpoint allows users to view details of their organization.
    Users can only view details of the organization they belong to.

    Requirements:
    - User must be authenticated
    - User must belong to the organization

    Args:
        organization_id: UUID of the organization to retrieve
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        OrganizationDetailResponse: Organization details

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized,
                      403 for forbidden, 404 for not found, 500 for server errors
    """
    try:
        service = OrganizationService(db)
        result = await service.get_organization_details(
            organization_id=organization_id,
            requesting_user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization details retrieved successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(f"Failed to get organization details for org_id={organization_id}: {str(e)}")
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
            f"Failed to retrieve organization details for org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organization details. Please try again later.",
        )


get_organization_details._custom_errors = get_organization_custom_errors
get_organization_details._custom_success = get_organization_custom_success
