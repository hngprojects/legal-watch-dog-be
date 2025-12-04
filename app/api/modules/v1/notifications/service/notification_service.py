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
        Get notifications for a user with optional filters.
        Returns (notifications, total_count).
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
        """Update a notification."""

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
        Get notification with full context for navigation.
        Includes related entities based on context fields.
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
            context["revision"] = revision.model_dump() if revision else None

        if notification.source_id:
            from app.api.modules.v1.scraping.models.source_model import Source

            source_query = select(Source).where(Source.id == notification.source_id)
            source_result = await db.execute(source_query)
            source = source_result.scalar_one_or_none()
            context["source"] = source.model_dump() if source else None

        if notification.organization_id:
            from app.api.modules.v1.organization.models.organization_model import Organization

            org_query = select(Organization).where(Organization.id == notification.organization_id)
            org_result = await db.execute(org_query)
            context["organization"] = org_result.scalar_one_or_none()

        if notification.change_diff_id:
            from app.api.modules.v1.scraping.models.change_diff import ChangeDiff

            diff_query = select(ChangeDiff).where(ChangeDiff.diff_id == notification.change_diff_id)
            diff_result = await db.execute(diff_query)
            context["change_diff"] = diff_result.scalar_one_or_none()

        return context
