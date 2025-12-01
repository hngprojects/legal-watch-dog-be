import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.role_exceptions import (
    CannotAssignRoleException,
    CannotManageHigherRoleException,
    InsufficientRoleException,
    MembershipNotFoundException,
    RoleHierarchyException,
    RoleNotFoundException,
    SelfManagementException,
)
from app.api.db.database import get_db
from app.api.modules.v1.organization.routes.docs.organization_route_docs import (
    create_organization_custom_errors,
    create_organization_custom_success,
    create_organization_responses,
    delete_organization_custom_errors,
    delete_organization_custom_success,
    delete_organization_responses,
    update_organization_custom_errors,
    update_organization_custom_success,
    update_organization_responses,
)
from app.api.modules.v1.organization.schemas.invitation_schema import (
    InvitationCreate,
    InvitationResponse,
)
from app.api.modules.v1.organization.schemas.member_schema import UpdateMemberRequest
from app.api.modules.v1.organization.schemas.organization_schema import (
    CreateOrganizationRequest,
    CreateOrganizationResponse,
    OrganizationDetailResponse,
    UpdateMemberRoleRequest,
    UpdateMemberStatusRequest,
    UpdateOrganizationRequest,
)
from app.api.modules.v1.organization.service.organization_service import OrganizationService
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.utils.organization_validations import check_user_permission
from app.api.utils.response_payloads import error_response, success_response
from app.api.utils.role_hierarchy import validate_role_hierarchy

router = APIRouter(prefix="/organizations", tags=["Organizations"])

logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=CreateOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=create_organization_responses,
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


create_organization._custom_errors = create_organization_custom_errors
create_organization._custom_success = create_organization_custom_success


@router.patch(
    "/{organization_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
    responses=update_organization_responses,
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


update_organization._custom_errors = update_organization_custom_errors
update_organization._custom_success = update_organization_custom_success


@router.post(
    "/{organization_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    background_task: BackgroundTasks,
    organization_id: uuid.UUID,
    payload: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a new user to the organization.

    This endpoint allows an admin to send an email invitation to a user.
    If the user is not registered, they will be prompted to create an account.

    Requirements:
    - User must be authenticated
    - User must be an admin of the organization or have 'invite_users' permission

    Args:
        organization_id: UUID of the organization to invite the user to
        payload: Invitation details (invited email, optional role_id)
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        InvitationResponse: Success response with invitation details

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized,
                      403 for forbidden, 500 for server errors
    """
    try:
        service = OrganizationService(db)

        result = await service.send_invitation(
            background_tasks=background_task,
            organization_id=organization_id,
            invited_email=payload.invited_email,
            inviter_id=current_user.id,
            role_name=payload.role_name,
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Invitation sent successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(f"Invitation failed for organization_id={organization_id}: {str(e)}")
        error_message = str(e)
        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "do not have permission" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        elif "already a member" in error_message.lower():
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Failed to send invitation for organization_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to send invitation. Please try again later.",
        )


@router.patch(
    "/{organization_id}/members/{user_id}/status",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def update_member_status(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateMemberStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Activate or deactivate a member's status within an organization.

    This endpoint allows an admin to change the active status of a member.

    Requirements:
    - User must be authenticated
    - User must have 'manage_users' or 'deactivate_users' permission in the organization
    - User must have higher role level than the target user

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the member whose status is to be updated
        payload: Request body containing the new `is_active` status
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        dict: Success message

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized,
                      403 for forbidden, 404 for not found, 500 for server errors
    """
    try:
        has_permission = await check_user_permission(
            db, current_user.id, organization_id, "manage_users"
        )
        if not has_permission:
            raise InsufficientRoleException(
                "You do not have permission to manage users in this organization"
            )

        if current_user.id == user_id:
            raise SelfManagementException("You cannot change your own membership status")

        await validate_role_hierarchy(
            db=db,
            current_user_id=current_user.id,
            target_user_id=user_id,
            organization_id=organization_id,
            action="deactivate",
        )

        await UserOrganizationCRUD.set_membership_status(
            db=db,
            user_id=user_id,
            organization_id=organization_id,
            is_active=payload.is_active,
        )
        await db.commit()

        status_message = "activated" if payload.is_active else "deactivated"
        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"{user_id} {status_message} successfully in org {organization_id}.",
        )

    except (
        RoleHierarchyException,
        InsufficientRoleException,
        SelfManagementException,
    ) as e:
        logger.warning(
            f"Authorization error updating status for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except MembershipNotFoundException as e:
        logger.warning(
            f"Membership not found for user_id={user_id} in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except RoleNotFoundException as e:
        logger.warning(
            f"Role not found for user_id={user_id} in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except ValueError as e:
        logger.warning(
            f"Validation error updating status for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Unexpected error updating user_id={user_id} status "
            f"in org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update member status. Please try again later.",
        )


@router.patch(
    "/{organization_id}/members/{user_id}/role",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def update_member_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a member's role within an organization.

    This endpoint allows an admin to assign a new role to a member.

    Requirements:
    - User must be authenticated
    - User must have 'assign_roles' permission in the organization
    - User must have higher role level than the target user
    - User must be able to assign the new role

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the member whose role is to be updated
        payload: Request body containing the new `role_name`
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        dict: Success message

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized,
                      403 for forbidden, 404 for not found, 500 for server errors
    """
    try:
        has_permission = await check_user_permission(
            db, current_user.id, organization_id, "assign_roles"
        )
        if not has_permission:
            raise InsufficientRoleException(
                "You do not have permission to assign roles in this organization"
            )

        if current_user.id == user_id:
            raise SelfManagementException("change your own role")

        role = await RoleCRUD.get_role_by_name_and_organization(
            db, payload.role_name, organization_id
        )
        if not role:
            raise RoleNotFoundException(
                f"Role '{payload.role_name}' not found in this organization"
            )

        await validate_role_hierarchy(
            db=db,
            current_user_id=current_user.id,
            target_user_id=user_id,
            organization_id=organization_id,
            action="assign_role",
            new_role_name=payload.role_name,
        )

        await UserOrganizationCRUD.update_user_role_in_organization(
            db=db,
            user_id=user_id,
            organization_id=organization_id,
            new_role_id=role.id,
        )
        await db.commit()

        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"{user_id} role updated: {payload.role_name} in org {organization_id}.",
        )

    except (
        CannotManageHigherRoleException,
        CannotAssignRoleException,
        InsufficientRoleException,
        SelfManagementException,
    ) as e:
        logger.warning(
            f"Authorization error updating role for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except (MembershipNotFoundException, RoleNotFoundException) as e:
        logger.warning(
            f"Not found error updating role for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except ValueError as e:
        logger.warning(
            f"Validation error updating role for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Unexpected error updating role for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update role. Please try again later.",
        )


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def update_member_details(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a member's details within an organization.

    This endpoint allows an admin to update a member's:
    - Name
    - Email (if not verified)
    - Department
    - Job Title

    Requirements:
    - User must be authenticated
    - User must have 'manage_users' permission in the organization
    - User must have higher role level than the target user (role hierarchy)

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the member to update
        payload: Request body containing fields to update
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        dict: Success message with updated details

    Raises:
        HTTPException: 400 for validation errors, 403 for forbidden, 404 for not found
    """
    try:
        has_permission = await check_user_permission(
            db, current_user.id, organization_id, "manage_users"
        )
        if not has_permission:
            raise InsufficientRoleException(
                "You do not have permission to manage users in this organization"
            )

        if current_user.id != user_id:
            await validate_role_hierarchy(
                db=db,
                current_user_id=current_user.id,
                target_user_id=user_id,
                organization_id=organization_id,
                action="manage",
            )

        # Prepare update dictionaries
        user_updates = {}
        if payload.name is not None:
            user_updates["name"] = payload.name
        if payload.email is not None:
            user_updates["email"] = payload.email

        membership_updates = {}
        if payload.department is not None:
            membership_updates["department"] = payload.department
        if payload.title is not None:
            membership_updates["title"] = payload.title

        if not user_updates and not membership_updates:
            raise ValueError("No fields provided for update")

        updated_user, updated_membership = await UserOrganizationCRUD.update_member_details(
            db=db,
            organization_id=organization_id,
            user_id=user_id,
            user_updates=user_updates,
            membership_updates=membership_updates,
        )
        await db.commit()

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Member details updated successfully",
            data={
                "user_id": str(updated_user.id),
                "name": updated_user.name,
                "email": updated_user.email,
                "department": updated_membership.department,
                "title": updated_membership.title,
            },
        )

    except (CannotManageHigherRoleException, InsufficientRoleException) as e:
        logger.warning(
            f"Authorization error updating details for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except (MembershipNotFoundException, RoleNotFoundException) as e:
        logger.warning(
            f"Not found error updating details for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except ValueError as e:
        logger.warning(
            f"Validation error updating details for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Unexpected error updating details for user_id={user_id} "
            f"in org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update member details. Please try again later.",
        )


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a member from an organization.

    This endpoint allows admin users to remove members from the organization
    using soft delete (membership record is kept but marked as deleted).

    Requirements:
    - User must be authenticated
    - User must have 'manage_users' permission in the organization
    - User must have higher role level than the target user
    - Cannot delete yourself

    Args:
        organization_id: UUID of the organization
        user_id: UUID of the member to delete
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 400 for validation errors, 403 for forbidden, 404 for not found
    """
    try:
        has_permission = await check_user_permission(
            db, current_user.id, organization_id, "manage_users"
        )
        if not has_permission:
            raise InsufficientRoleException(
                "You do not have permission to manage users in this organization"
            )

        if current_user.id == user_id:
            raise SelfManagementException("You cannot delete yourself from the organization")

        await validate_role_hierarchy(
            db=db,
            current_user_id=current_user.id,
            target_user_id=user_id,
            organization_id=organization_id,
            action="delete",
        )

        await UserOrganizationCRUD.soft_delete_member(
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )
        await db.commit()

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except (
        CannotManageHigherRoleException,
        InsufficientRoleException,
        SelfManagementException,
    ) as e:
        logger.warning(
            f"Authorization error deleting member user_id={user_id} "
            f"from org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except (MembershipNotFoundException, RoleNotFoundException) as e:
        logger.warning(
            f"Not found error deleting member user_id={user_id} "
            f"from org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=e.status_code,
            message=e.message,
        )

    except ValueError as e:
        logger.warning(
            f"Validation error deleting member user_id={user_id} "
            f"from org_id={organization_id}: {str(e)}"
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Unexpected error deleting member user_id={user_id} "
            f"from org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete member. Please try again later.",
        )


@router.get(
    "/{organization_id}",
    status_code=status.HTTP_200_OK,
)
async def get_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get organization details.

    Returns the details of a specific organization, including:
    - Basic info (name, industry, etc.)
    - Profile info (location, plan, logo_url)
    - Projects count

    Requirements:
    - User must be a member of the organization
    """
    try:
        service = OrganizationService(db)
        org_details = await service.get_organization_details(
            organization_id=organization_id, requesting_user_id=current_user.id
        )
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization details retrieved successfully",
            data=OrganizationDetailResponse(**org_details),
        )

    except ValueError as e:
        logger.warning(f"Failed to get organization org_id={organization_id}: {str(e)}")
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
            f"Failed to retrieve organization org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organization details. Please try again later.",
        )


@router.get(
    "/{organization_id}/users",
    status_code=status.HTTP_200_OK,
)
async def get_all_users_in_organization(
    organization_id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="Page number (minimum: 1)"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
    active_only: bool = Query(default=True, description="Only return active members"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all users in an organization.

    Returns all users who are members of the specified organization,
    along with their roles and membership details.

    Requirements:
    - User must be authenticated
    - User must be a member of the organization to view other members

    Args:
        organization_id: UUID of the organization
        page: Page number (default: 1)
        limit: Items per page (default: 10, max: 100)
        active_only: Only return active members (default: True)
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with paginated list of users

    Raises:
        HTTPException: 400 for validation errors, 403 for forbidden,
                      404 for not found, 500 for server errors
    """
    try:
        service = OrganizationService(db)
        result = await service.get_organization_users(
            organization_id=organization_id,
            requesting_user_id=current_user.id,
            page=page,
            limit=limit,
            active_only=active_only,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization users retrieved successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(f"Failed to get users for org_id={organization_id}: {str(e)}")
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
            f"Failed to retrieve users for org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve organization users. Please try again later.",
        )


@router.delete(
    "/{organization_id}",
    status_code=status.HTTP_200_OK,
    responses=delete_organization_responses,
)
async def delete_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an organization.

    This endpoint allows organization admins to permanently delete their organization.
    All associated data (memberships, invitations, roles, projects) will be cascaded.

    Requirements:
    - User must be authenticated
    - User must be an admin of the organization
    - Organization must have no active members besides the current user

    Args:
        organization_id: UUID of the organization to delete
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with deletion confirmation

    Raises:
        HTTPException: 400 for validation errors, 403 for forbidden,
                      404 for not found, 500 for server errors
    """
    try:
        service = OrganizationService(db)

        await service.delete_organization(
            organization_id=organization_id,
            requesting_user_id=current_user.id,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        logger.warning(f"Organization deletion failed for org_id={organization_id}: {str(e)}")
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "admin" in error_message.lower() or "permission" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Failed to delete organization org_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete organization. Please try again later.",
        )


delete_organization._custom_errors = delete_organization_custom_errors
delete_organization._custom_success = delete_organization_custom_success
