import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.ticket_external_access_schema import (
    CreateExternalAccessRequest,
    ExternalAccessResponse,
    ExternalTicketDetailResponse,
    RevokeExternalAccessRequest,
)
from app.api.modules.v1.tickets.service.ticket_external_access_service import (
    TicketExternalAccessService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger("app")


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets - External Access"],
    dependencies=[Depends(require_billing_access)],
)


public_router = APIRouter(
    prefix="/external/tickets",
    tags=["Tickets - External Access (Public)"],
)


@router.post(
    "/{ticket_id}/external-access",
    response_model=ExternalAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_access(
    ticket_id: UUID,
    payload: CreateExternalAccessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a secure external access link for a ticket.

    This endpoint allows organization members to generate tokenized links
    that grant external users (non-members) read-only access to specific tickets.

    External users can view:
    - Ticket details (title, description, content, status, priority)
    - Ticket revisions and change history
    - Discussion threads

    External users cannot:
    - Access other tickets or organization data
    - Modify ticket data
    - See internal user information

    Requirements:
        - User must be authenticated
        - User must have INVITE_PARTICIPANTS permission
        - User must be a member of the ticket's organization
        - Ticket must exist

    Args:
        ticket_id: UUID of the ticket to share
        payload: Request body with optional email and expiration
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ExternalAccessResponse containing the secure token and access URL
    """
    try:
        service = TicketExternalAccessService(db)
        result = await service.create_external_access(
            ticket_id=ticket_id,
            created_by_user_id=current_user.id,
            email=payload.email,
            expires_in_days=payload.expires_in_days,
        )

        logger.info(
            f"External access created by user {current_user.id} for ticket {ticket_id}",
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
                "email": payload.email,
            },
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="External access link created successfully",
            data=result.model_dump(),
        )

    except ValueError as e:
        logger.warning(
            f"Validation error in create_external_access: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error creating external access: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="Failed to create external access link. Please try again.",
        )


@router.get(
    "/{ticket_id}/external-access",
    response_model=list[ExternalAccessResponse],
    status_code=status.HTTP_200_OK,
)
async def list_external_accesses(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all external access links for a ticket.

    Returns all external access tokens created for the ticket,
    including active, expired, and revoked tokens.

    Requirements:
        - User must be authenticated
        - User must be a member of the ticket's organization

    Args:
        ticket_id: UUID of the ticket
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        List of ExternalAccessResponse objects
    """
    try:
        service = TicketExternalAccessService(db)
        accesses = await service.list_external_accesses(ticket_id=ticket_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"Found {len(accesses)} external access link(s)",
            data={"accesses": [access.model_dump() for access in accesses]},
        )

    except Exception as e:
        logger.error(
            f"Error listing external accesses: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="Failed to retrieve external access links.",
        )


@router.delete(
    "/external-access/revoke",
    status_code=status.HTTP_200_OK,
)
async def revoke_external_access(
    payload: RevokeExternalAccessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke an external access link.

    Immediately invalidates the access token, preventing further access.
    Previously accessed data remains visible in the external user's browser
    until they refresh.

    Requirements:
        - User must be authenticated
        - User must be a member of the ticket's organization

    Args:
        payload: Request body with access_id to revoke
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        Success message
    """
    try:
        service = TicketExternalAccessService(db)
        await service.revoke_external_access(
            access_id=payload.access_id,
            current_user_id=current_user.id,
        )

        logger.info(
            f"External access revoked by user {current_user.id}",
            extra={
                "user_id": str(current_user.id),
                "access_id": str(payload.access_id),
            },
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="External access link revoked successfully",
        )

    except ValueError as e:
        logger.warning(
            f"Validation error in revoke_external_access: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "access_id": str(payload.access_id),
            },
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error revoking external access: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "access_id": str(payload.access_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="Failed to revoke external access. Please try again.",
        )


@public_router.get(
    "/{token}",
    response_model=ExternalTicketDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_ticket_by_external_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Access a ticket using an external access token (PUBLIC ENDPOINT).

    This endpoint allows external users (non-members) to view ticket details
    without authentication. The token serves as the authorization mechanism.

    Returns limited ticket information:
    - Basic ticket details (title, description, content, status, priority)
    - Organization and project names
    - Timestamps

    Does NOT return:
    - Internal user details
    - Organization internal data
    - Other tickets or projects

    Security:
        - Token must be valid and not expired
        - Token must not be revoked
        - Each access is logged and tracked

    Args:
        token: External access token from the URL
        db: Database session (injected)

    Returns:
        ExternalTicketDetailResponse with limited ticket data
    """
    try:
        service = TicketExternalAccessService(db)
        ticket_data = await service.get_ticket_by_token(token=token)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Ticket retrieved successfully",
            data=ticket_data.model_dump(),
        )

    except ValueError as e:
        logger.warning(
            f"Invalid external token access attempt: {str(e)}",
            extra={"token_prefix": token[:20] if len(token) > 20 else token},
        )
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error accessing ticket with external token: {str(e)}",
            exc_info=True,
            extra={"token_prefix": token[:20] if len(token) > 20 else token},
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="Failed to retrieve ticket. Please try again or contact support.",
        )
