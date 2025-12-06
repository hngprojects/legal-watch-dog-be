import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
)
from app.api.modules.v1.notifications.schemas.notification_schema import (
    NotificationFilter,
    NotificationUpdate,
)


class NotificationService:
    """Service for reading and managing notifications."""

    @staticmethod
    async def get_notification_by_id(
        db: AsyncSession, notification_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Notification]:
        """Get a notification by ID, optionally filtered by user."""

        query = select(Notification).where(Notification.notification_id == notification_id)

        if user_id:
            query = query.where(Notification.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        filters: Optional[NotificationFilter] = None,
        skip: int = 0,
        limit: int = 50,
        order_by_latest: bool = True,
    ) -> Tuple[List[Notification], int]:
        """
        Retrieve notifications for a specific user with optional filtering, pagination,
        and ordering preferences.

        This method returns both the list of notifications and the total count
        matching the filters (without pagination applied). It supports filtering by
        status, notification type, read status, date range, organization, and source ID.

        Args:
            db (AsyncSession):
                The active SQLAlchemy asynchronous database session.
            user_id (uuid.UUID):
                The unique identifier of the user whose notifications are being retrieved.
            filters (Optional[NotificationFilter], optional):
                A set of filters to narrow down the notifications query. Defaults to None.
            skip (int, optional):
                The number of records to skip (for pagination). Defaults to 0.
            limit (int, optional):
                The maximum number of notifications to return. Defaults to 50.
            order_by_latest (bool, optional):
                Whether to order results by most recent notifications first. Defaults to True.

        Returns:
            Tuple[List[Notification], int]:
                A tuple where:
                - The first element is the list of notifications returned for the user.
                - The second element is the total number of matching notifications
                before pagination.

        Raises:
            SQLAlchemyError: If a database error occurs during query execution.

        """

        query = select(Notification).where(Notification.user_id == user_id)
        count_query = (
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )

        if filters:
            conditions = []

            if filters.status:
                conditions.append(Notification.status == filters.status)

            if filters.notification_type:
                conditions.append(Notification.notification_type == filters.notification_type)

            if filters.is_read is not None:
                if filters.is_read:
                    conditions.append(Notification.read_at.is_not(None))
                else:
                    conditions.append(Notification.read_at.is_(None))

            if filters.from_date:
                conditions.append(Notification.created_at >= filters.from_date)

            if filters.to_date:
                conditions.append(Notification.created_at <= filters.to_date)

            if filters.organization_id:
                conditions.append(Notification.organization_id == filters.organization_id)

            if filters.source_id:
                conditions.append(Notification.source_id == filters.source_id)

            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))

        if order_by_latest:
            query = query.order_by(desc(Notification.created_at))

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        notifications = result.scalars().all()

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return list(notifications), total

    @staticmethod
    async def mark_as_read(
        db: AsyncSession, notification_ids: List[uuid.UUID], user_id: uuid.UUID
    ) -> int:
        """Mark notifications as read. Returns count of updated notifications."""

        query = select(Notification).where(
            and_(
                Notification.notification_id.in_(notification_ids),
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )

        result = await db.execute(query)
        notifications = result.scalars().all()

        read_time = datetime.now(timezone.utc)
        for notification in notifications:
            notification.read_at = read_time
            notification.status = NotificationStatus.READ

        await db.commit()

        return len(notifications)

    @staticmethod
    async def mark_all_as_read(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Mark all unread notifications as read for a user."""

        query = select(Notification).where(
            and_(Notification.user_id == user_id, Notification.read_at.is_(None))
        )

        result = await db.execute(query)
        notifications = result.scalars().all()

        read_time = datetime.now(timezone.utc)
        for notification in notifications:
            notification.read_at = read_time
            notification.status = NotificationStatus.READ

        await db.commit()

        return len(notifications)

    @staticmethod
    async def update_notification(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        update_data: NotificationUpdate,
    ) -> Optional[Notification]:
        """
        Update fields of a specific user-owned notification.

        This method looks up the notification by ID and user ID to ensure that the
        user has permission to modify it. Only the fields provided in the
        `NotificationUpdate` schema will be updated. After updating, the changes
        are committed and the refreshed notification instance is returned.

        Args:
            db (AsyncSession):
                The active SQLAlchemy asynchronous database session.
            notification_id (uuid.UUID):
                The unique identifier of the notification to update.
            user_id (uuid.UUID):
                The ID of the user who owns the notification. Used to prevent
                unauthorized updates.
            update_data (NotificationUpdate):
                The data specifying which fields should be updated (e.g., status,
                read timestamp).

        Returns:
            Optional[Notification]:
                The updated notification object if found, otherwise `None` if the
                notification does not exist or does not belong to the user.

        Raises:
            SQLAlchemyError: If a database-level error occurs during update or commit.
        """

        notification = await NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )

        if not notification:
            return None

        if update_data.status:
            notification.status = update_data.status

        if update_data.read_at:
            notification.read_at = update_data.read_at

        await db.commit()
        await db.refresh(notification)

        return notification

    @staticmethod
    async def delete_notification(
        db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Delete a notification. Returns True if deleted, False if not found."""

        notification = await NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )

        if not notification:
            return False

        await db.delete(notification)
        await db.commit()

        return True

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Get count of unread notifications for a user."""

        query = (
            select(func.count())
            .select_from(Notification)
            .where(and_(Notification.user_id == user_id, Notification.read_at.is_(None)))
        )

        result = await db.execute(query)
        return result.scalar()

    @staticmethod
    async def get_notification_stats(db: AsyncSession, user_id: uuid.UUID) -> Dict:
        """Get statistics about user notifications."""

        total_query = (
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        unread_count = await NotificationService.get_unread_count(db, user_id)

        pending_query = (
            select(func.count())
            .select_from(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.status == NotificationStatus.PENDING,
                )
            )
        )
        pending_result = await db.execute(pending_query)
        pending = pending_result.scalar()

        type_query = (
            select(Notification.notification_type, func.count(Notification.notification_id))
            .where(Notification.user_id == user_id)
            .group_by(Notification.notification_type)
        )

        type_result = await db.execute(type_query)
        by_type = {row[0]: row[1] for row in type_result.all()}

        return {
            "total_notifications": total,
            "unread_count": unread_count,
            "pending_count": pending,
            "by_type": by_type,
        }

    @staticmethod
    async def get_notification_with_context(
        db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Dict]:
        """
        Retrieve a notification along with its related contextual entities.

        This method first ensures the notification exists and belongs to the user.
        It then loads related context objects such as the associated revision,
        source, organization, or change diff—depending on which fields are present
        in the notification. Each related entity is added to the returned
        dictionary, providing full context for UI navigation or detailed inspection.

        Args:
            db (AsyncSession):
                The active SQLAlchemy asynchronous database session.
            notification_id (uuid.UUID):
                The ID of the notification to retrieve.
            user_id (uuid.UUID):
                The owner of the notification. Used to ensure access control.

            Returns:
                Optional[Dict]:
                    A dictionary containing:
                        - "notification": The notification object.
                        - "revision": Serialized revision data (if available).
                        - "source": Serialized source data (if available).
                        - "organization": The related organization object (if available).
                        - "change_diff": The related change diff object (if available).
                    Returns `None` if the notification does not exist or does not
                    belong to the user.

        Raises:
            SQLAlchemyError: If any database query fails.
        """

        notification = await NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )

        if not notification:
            return None

        context = {"notification": notification}

        if notification.revision_id:
            from app.api.modules.v1.scraping.models.data_revision import DataRevision

            rev_query = select(DataRevision).where(DataRevision.id == notification.revision_id)
            rev_result = await db.execute(rev_query)
            revision = rev_result.scalar_one_or_none()
            if revision:
                context["revision"] = revision.model_dump()

        if notification.source_id:
            from app.api.modules.v1.scraping.models.source_model import Source

            source_query = select(Source).where(Source.id == notification.source_id)
            source_result = await db.execute(source_query)
            source = source_result.scalar_one_or_none()
            if source:
                context["source"] = source.model_dump()

        if notification.organization_id:
            from app.api.modules.v1.organization.models.organization_model import Organization

            org_query = select(Organization).where(Organization.id == notification.organization_id)
            org_result = await db.execute(org_query)
            org = org_result.scalar_one_or_none()
            if org:
                context["organization"] = org.model_dump()

        if notification.change_diff_id:
            from app.api.modules.v1.scraping.models.change_diff import ChangeDiff

            diff_query = select(ChangeDiff).where(ChangeDiff.diff_id == notification.change_diff_id)
            diff_result = await db.execute(diff_query)
            diff = diff_result.scalar_one_or_none()
            if diff:
                context["change_diff"] = diff.model_dump()

        return context
