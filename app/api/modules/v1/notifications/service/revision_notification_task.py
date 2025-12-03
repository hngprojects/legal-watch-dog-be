import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.api.core.dependencies.send_mail import send_email
from app.api.db.database import AsyncSessionLocal, engine
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
)
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


async def send_revision_notifications(revision_id: str):
    """
    Send notifications to ALL users in the project for a data revision.

    All users with access to the project will receive notifications when
    a source in their jurisdiction has a data revision.

    Args:
        revision_id: UUID string of the data revision

    Raises:
        SQLAlchemyError: If there is a database error during processing
    """
    try:
        async with AsyncSessionLocal() as session:
            revision_uuid = UUID(revision_id)

            revision_result = await session.execute(
                select(DataRevision).where(DataRevision.id == revision_uuid)
            )
            revision = revision_result.scalar_one_or_none()
            if not revision:
                logger.warning(f"No data revision found with id {revision_id}")
                return

            source_result = await session.execute(
                select(Source).where(Source.id == revision.source_id)
            )
            source = source_result.scalar_one_or_none()
            if not source:
                logger.warning(f"No source found for revision {revision_id}")
                return

            jurisdiction_result = await session.execute(
                select(Jurisdiction).where(Jurisdiction.id == source.jurisdiction_id)
            )
            jurisdiction = jurisdiction_result.scalar_one_or_none()
            if not jurisdiction:
                logger.warning(f"No jurisdiction found for revision {revision_id}")
                return

            project_result = await session.execute(
                select(Project).where(Project.id == jurisdiction.project_id)
            )
            project = project_result.scalar_one_or_none()
            if not project:
                logger.warning(f"No project found for revision {revision_id}")
                return

            project_users_result = await session.execute(
                select(ProjectUser).where(ProjectUser.project_id == project.id)
            )
            project_users = project_users_result.scalars().all()
            if not project_users:
                logger.info(f"No users associated with project {project.id}")
                return

            user_ids = [pu.user_id for pu in project_users]

            logger.info(
                f"Found {len(user_ids)} user(s) in project {project.id} "
                f"(organization: {getattr(project, 'organization_id', 'N/A')})"
            )

            notifications_sent = 0
            notifications_skipped = 0
            notifications_failed = 0

            for user_id in user_ids:
                user_result = await session.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()
                if not user:
                    logger.warning(f"User {user_id} not found, skipping")
                    continue

                # Idempotency check - check if notification already exists
                existing_result = await session.execute(
                    select(Notification).where(
                        Notification.revision_id == revision_uuid,
                        Notification.user_id == user.id,
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    logger.info(
                        f"Notification already exists for user {user.email} "
                        f"(notification_id: {existing.notification_id})"
                    )

                    # IDEMPOTENCY: Check if email was already sent
                    if existing.status == NotificationStatus.SENT:
                        logger.info(
                            f"Email already sent for notification {existing.notification_id}"
                        )
                        notifications_skipped += 1
                        continue
                    elif existing.status == NotificationStatus.FAILED:
                        logger.info(f"Retrying failed notification {existing.notification_id}")
                        notification = existing
                    else:
                        logger.info(
                            f"Found pending notification {existing.notification_id}, sending email"
                        )
                        notification = existing
                else:
                    notification = Notification(
                        revision_id=revision_uuid,
                        user_id=user.id,
                        message=revision.ai_summary or "New revision available",
                        status=NotificationStatus.PENDING,
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                    session.add(notification)
                    await session.commit()
                    await session.refresh(notification)
                    logger.info(
                        f"Created notification {notification.notification_id} for user {user.email}"
                    )

                email_context = {
                    "user_name": user.name or getattr(user, "username", "User"),
                    "ai_summary": revision.ai_summary,
                    "subject": "New Revision Available",
                }
                try:
                    success = await send_email(
                        template_name="revision_notification.html",
                        subject="New Revision Available",
                        recipient=user.email,
                        context=email_context,
                    )
                    notification.status = (
                        NotificationStatus.SENT if success else NotificationStatus.FAILED
                    )
                    notification.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    session.add(notification)
                    await session.commit()
                    await session.refresh(notification)

                    if success:
                        notifications_sent += 1
                        logger.info(
                            f"✓ Notification {notification.notification_id} sent to {user.email}"
                        )
                    else:
                        notifications_failed += 1
                        logger.error(
                            f"✗ Failed to send notification {notification.notification_id} "
                            f"to {user.email}"
                        )
                except Exception as e:
                    notification.status = NotificationStatus.FAILED
                    session.add(notification)
                    await session.commit()
                    notifications_failed += 1
                    logger.error(
                        f"✗ Exception sending notification {notification.notification_id} "
                        f"to {user.email}: {str(e)}"
                    )

            logger.info(
                f"Notification summary for revision {revision_id}: "
                f"Sent: {notifications_sent}, "
                f"Skipped: {notifications_skipped}, Failed: {notifications_failed}"
            )

    except SQLAlchemyError as e:
        logger.error(f"Database error sending notifications for revision {revision_id}: {str(e)}")
        raise
    finally:
        await engine.dispose()


@shared_task(bind=True, name="send_revision_notifications", max_retries=3)
def send_revision_notifications_task(self, revision_id: str):
    """
    Celery task wrapper for sending revision notifications to ALL project users.

    Args:
        revision_id: UUID string of the data revision

    Returns:
        None

    Raises:
        Retries the task up to 3 times with 60 second delay on failure
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(send_revision_notifications(revision_id))
        logger.info(f"Successfully processed notifications for revision {revision_id}")
        return result
    except Exception as exc:
        logger.error(f"Error processing notifications for revision {revision_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)
    