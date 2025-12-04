import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.notifications.routes.docs.notification_route_docs import (
    get_notification_context_custom_errors,
    get_notification_context_custom_success,
    get_notification_context_responses,
    get_notification_custom_errors,
    get_notification_custom_success,
    get_notification_responses,
    get_notification_stats_custom_errors,
    get_notification_stats_custom_success,
    get_notification_stats_responses,
    get_notifications_custom_errors,
    get_notifications_custom_success,
    get_notifications_responses,
    mark_all_read_custom_errors,
    mark_all_read_custom_success,
    mark_all_read_responses,
    mark_notifications_read_custom_errors,
    mark_notifications_read_custom_success,
    mark_notifications_read_responses,
    update_notification_custom_errors,
    update_notification_custom_success,
    update_notification_responses,
)
from app.api.modules.v1.notifications.schemas.notification_schema import (
    NotificationContextResponse,
    NotificationFilter,
    NotificationListResponse,
    NotificationMarkRead,
    NotificationResponse,
    NotificationStats,
    NotificationUpdate,
)
from app.api.modules.v1.notifications.service.notification_service import (
    NotificationService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user notifications",
    responses=get_notifications_responses,
)
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    organization_id: Optional[uuid.UUID] = Query(None, description="Filter by organization"),
    source_id: Optional[uuid.UUID] = Query(None, description="Filter by source"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve notifications for the authenticated user with support for pagination and filtering.

    This endpoint allows clients to fetch a paginated list of notifications belonging
    to the current user. Filters can be applied based on notification status, type,
    read state, organization, or source. The response also includes the total count
    of notifications matching the filters and the user's unread notification count.

    Requirements:
    - User must be authenticated (verified via JWT)

    Args:
        page (int):
            The page number to retrieve. Must be 1 or greater.
        page_size (int):
            Number of items to return per page. Must be between 1 and 100.
        status_filter (Optional[str]):
            Filter notifications by status (e.g., "PENDING", "READ", etc.).
        notification_type (Optional[str]):
            Filter by notification type category.
        is_read (Optional[bool]):
            Filter by read state. `True` for read notifications, `False` for unread.
        organization_id (Optional[uuid.UUID]):
            Filter notifications linked to a specific organization.
        source_id (Optional[uuid.UUID]):
            Filter notifications linked to a specific source.
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        NotificationListResponse:
            A structured response containing:
            - `notifications`: The paginated list of notifications.
            - `total`: Total notifications matching the filters (before pagination).
            - `page`: Current page number.
            - `page_size`: Page size used for pagination.
            - `unread_count`: Total unread notifications for the user.

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized, 500 for server errors
    """
    try:
        user_id = current_user.id

        filters = NotificationFilter(
            status=status_filter,
            notification_type=notification_type,
            is_read=is_read,
            organization_id=organization_id,
            source_id=source_id,
        )

        skip = (page - 1) * page_size
        notifications, total = await NotificationService.get_user_notifications(
            db=db, user_id=user_id, filters=filters, skip=skip, limit=page_size
        )

        unread_count = await NotificationService.get_unread_count(db, user_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Notifications retrieved successfully",
            data=NotificationListResponse(
                notifications=notifications,
                total=total,
                page=page,
                page_size=page_size,
                unread_count=unread_count,
            ),
        )

    except ValueError as e:
        logger.warning(f"Failed to retrieve notifications for user_id={current_user.id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to retrieve notifications for user_id={current_user.id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve notifications. Please try again later.",
        )


get_notifications._custom_errors = get_notifications_custom_errors
get_notifications._custom_success = get_notifications_custom_success


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification by ID",
    responses=get_notification_responses,
)
async def get_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific notification by ID.

    This endpoint retrieves detailed information about a single notification.
    Users can only access their own notifications.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID):
            The unique identifier of the notification to retrieve.
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        NotificationResponse:
            The notification details including content, status, timestamps, etc.

    Raises:
        HTTPException: 401 for unauthorized, 404 for not found, 500 for server errors
    """
    try:
        user_id = current_user.id

        notification = await NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )

        if not notification:
            logger.warning(
                f"Notification not found: notification_id={notification_id}, user_id={user_id}"
            )
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notification not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Notification retrieved successfully",
            data=notification,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to retrieve notification {notification_id} for user_id={user_id}: {str(e)}"
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to retrieve notification {notification_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve notification. Please try again later.",
        )


get_notification._custom_errors = get_notification_custom_errors
get_notification._custom_success = get_notification_custom_success


@router.get(
    "/{notification_id}/context",
    response_model=NotificationContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification with full context",
    responses=get_notification_context_responses,
)
async def get_notification_with_context(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get notification with full context including related entities.

    This endpoint provides comprehensive information about a notification,
    including all related entities such as projects, sources, revisions, etc.
    This context allows clients to navigate directly to the relevant resource.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID):
            The unique identifier of the notification.
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        NotificationContextResponse:
            Notification details with full contextual information about
            related entities (project, source, revision, organization, etc.).

    Raises:
        HTTPException: 401 for unauthorized, 404 for not found, 500 for server errors
    """
    try:
        user_id = current_user.id

        context = await NotificationService.get_notification_with_context(
            db, notification_id, user_id
        )

        if not context:
            logger.warning(
                f"Notification context not found: notification_id={notification_id}, "
                f"user_id={user_id}"
            )
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notification not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Notification context retrieved successfully",
            data=context,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to retrieve notification context {notification_id} "
            f"for user_id={user_id}: {str(e)}"
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to retrieve notification context {notification_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve notification context. Please try again later.",
        )


get_notification_with_context._custom_errors = get_notification_context_custom_errors
get_notification_with_context._custom_success = get_notification_context_custom_success


@router.patch(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update notification",
    responses=update_notification_responses,
)
async def update_notification(
    notification_id: uuid.UUID,
    update_data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a notification.

    This endpoint allows users to update notification properties such as
    marking it as read/unread or changing its status.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID):
            The unique identifier of the notification to update.
        update_data (NotificationUpdate):
            The fields to update (e.g., is_read, status).
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        NotificationResponse:
            The updated notification details.

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized,
                      404 for not found, 500 for server errors
    """
    try:
        user_id = current_user.id

        notification = await NotificationService.update_notification(
            db, notification_id, user_id, update_data
        )

        if not notification:
            logger.warning(
                f"Notification not found for update: notification_id={notification_id}, "
                f"user_id={user_id}"
            )
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notification not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Notification updated successfully",
            data=notification,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to update notification {notification_id} for user_id={user_id}: {str(e)}"
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to update notification {notification_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update notification. Please try again later.",
        )


update_notification._custom_errors = update_notification_custom_errors
update_notification._custom_success = update_notification_custom_success


@router.post(
    "/mark-read",
    status_code=status.HTTP_200_OK,
    summary="Mark notifications as read",
    responses=mark_notifications_read_responses,
)
async def mark_notifications_read(
    mark_data: NotificationMarkRead,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark one or more notifications as read.

    This endpoint allows users to mark multiple notifications as read in a single request.
    Only notifications belonging to the current user will be affected.

    Requirements:
    - User must be authenticated
    - User must own the notifications

    Args:
        mark_data (NotificationMarkRead):
            Request body containing a list of notification IDs to mark as read.
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        dict:
            Success message with the count of notifications marked as read.
            Format: {"message": str, "count": int}

    Raises:
        HTTPException: 400 for validation errors, 401 for unauthorized, 500 for server errors
    """
    try:
        user_id = current_user.id

        if not mark_data.notification_ids:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No notification IDs provided",
            )

        count = await NotificationService.mark_as_read(db, mark_data.notification_ids, user_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"Marked {count} notification(s) as read",
            data={"count": count},
        )

    except ValueError as e:
        logger.warning(f"Failed to mark notifications as read for user_id={user_id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to mark notifications as read for user_id={user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to mark notifications as read. Please try again later.",
        )


mark_notifications_read._custom_errors = mark_notifications_read_custom_errors
mark_notifications_read._custom_success = mark_notifications_read_custom_success


@router.post(
    "/mark-all-read",
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    responses=mark_all_read_responses,
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Mark all unread notifications as read for the current user.

    This endpoint marks all notifications belonging to the authenticated user
    that are currently unread as read. This is useful for "clear all" functionality.

    Requirements:
    - User must be authenticated

    Args:
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        dict:
            Success message with the count of notifications marked as read.
            Format: {"message": str, "count": int}

    Raises:
        HTTPException: 401 for unauthorized, 500 for server errors
    """
    try:
        user_id = current_user.id

        count = await NotificationService.mark_all_as_read(db, user_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"Marked {count} notification(s) as read",
            data={"count": count},
        )

    except ValueError as e:
        logger.warning(f"Failed to mark all notifications as read for user_id={user_id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to mark all notifications as read for user_id={user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to mark all notifications as read. Please try again later.",
        )


mark_all_read._custom_errors = mark_all_read_custom_errors
mark_all_read._custom_success = mark_all_read_custom_success


@router.delete(
    "/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete notification"
)
async def delete_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a notification.

    This endpoint allows users to delete a specific notification.
    The notification is permanently removed from the database.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID):
            The unique identifier of the notification to delete.
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 401 for unauthorized, 404 for not found, 500 for server errors
    """
    try:
        user_id = current_user.id

        deleted = await NotificationService.delete_notification(db, notification_id, user_id)

        if not deleted:
            logger.warning(
                f"Notification not found for deletion: notification_id={notification_id}, "
                f"user_id={user_id}"
            )
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notification not found",
            )

        return None

    except ValueError as e:
        logger.warning(
            f"Failed to delete notification {notification_id} for user_id={user_id}: {str(e)}"
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to delete notification {notification_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete notification. Please try again later.",
        )


@router.get(
    "/stats",
    response_model=NotificationStats,
    status_code=status.HTTP_200_OK,
    summary="Get notification statistics",
    responses=get_notification_stats_responses,
)
async def get_notification_stats(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get statistics about the current user's notifications.

    This endpoint provides aggregated statistics about the user's notifications,
    such as total count, unread count, counts by type, counts by status, etc.
    Useful for dashboard displays and notification badges.

    Requirements:
    - User must be authenticated

    Args:
        db (AsyncSession):
            Database session dependency.
        current_user (User):
            The authenticated user from the request context.

    Returns:
        NotificationStats:
            Statistical information about the user's notifications including:
            - Total notification count
            - Unread count
            - Counts grouped by type
            - Counts grouped by status
            - Recent activity metrics

    Raises:
        HTTPException: 401 for unauthorized, 500 for server errors
    """
    try:
        user_id = current_user.id

        stats = await NotificationService.get_notification_stats(db, user_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Notification statistics retrieved successfully",
            data=stats,
        )

    except ValueError as e:
        logger.warning(f"Failed to retrieve notification stats for user_id={user_id}: {str(e)}")
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            f"Failed to retrieve notification stats for user_id={user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve notification statistics. Please try again later.",
        )


get_notification_stats._custom_errors = get_notification_stats_custom_errors
get_notification_stats._custom_success = get_notification_stats_custom_success
