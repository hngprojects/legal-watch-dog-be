import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.organization.schemas.organization_schema import (
    CreateOrganizationRequest,
    CreateOrganizationResponse,
    OrganizationDetailResponse,
    UpdateOrganizationRequest,
)
from app.api.modules.v1.organization.service.organization_service import OrganizationService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(prefix="/organizations", tags=["Organizations"])

logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=CreateOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    payload: CreateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new organization.

    This endpoint allows verified users without an organization to create one.
    The user who creates the organization automatically becomes the admin.

    Requirements:
    - User must be authenticated (verified via JWT)
    - User email must be verified
    - User must not already belong to an organization
    - Organization name must be unique

    Args:
        payload: Organization creation request with name and optional industry
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        OrganizationResponse: Success response with organization details

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized, 500 for server errors
    """
    try:
        service = OrganizationService(db)
        user_id = current_user.id
        result = await service.create_organization(
            user_id=user_id,
            name=payload.name,
            industry=payload.industry,
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Organization created successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(f"Organization creation validation failed for user_id={user_id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to create organization for user_id={user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Organization creation failed. Please try again later.",
        )


@router.get(
    "/admin",
    status_code=status.HTTP_200_OK,
)
async def get_admin_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get organizations where the user is an Admin.
    """
    try:
        service = OrganizationService(db)
        result = await service.get_admin_organization(
            user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization retrieved successfully",
            data=result,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch organizations for user_id={current_user.id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organizations",
        )


@router.get(
    "/user/memberships",
    status_code=status.HTTP_200_OK,
)
async def get_user_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all organizations the current user is a member of.

    Returns all organizations where the user has an active membership,
    along with their role in each organization.
    """
    try:
        service = OrganizationService(db)
        result = await service.get_user_organizations(
            user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organizations retrieved successfully",
            data=result,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch organizations for user_id={current_user.id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organizations",
        )


@router.get(
    "/{organization_id:uuid}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
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


@router.patch(
    "/{organization_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def update_organization(
    organization_id: uuid.UUID,
    payload: UpdateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update organization details.

    This endpoint allows admin users to update their organization's details.
    Only users with 'write' permission on organization can update it.

    Requirements:
    - User must be authenticated
    - User must belong to the organization
    - User must be an admin on the organization

    Args:
        organization_id: UUID of the organization to update
        payload: Organization update request with optional fields
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        OrganizationDetailResponse: Updated organization details

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized,
                      403 for forbidden, 404 for not found, 500 for server errors
    """
    try:
        service = OrganizationService(db)
        result = await service.update_organization(
            organization_id=organization_id,
            requesting_user_id=current_user.id,
            name=payload.name,
            industry=payload.industry,
            is_active=payload.is_active,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization updated successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(f"Failed to update organization org_id={organization_id}: {str(e)}")
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif (
            "do not have access" in error_message.lower()
            or "do not have permission" in error_message.lower()
        ):
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Failed to update organization org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update organization. Please try again later.",
        )
