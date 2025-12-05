import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.api.core.dependencies.send_mail import send_email
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


async def send_scrape_failure_notifications(
    source_id: str, job_id: str, error_message: str
):
    """
    Send notifications to ALL users in the project when a scrape job fails.

    All users with access to the project will receive notifications when
    a source scrape fails in their jurisdiction.

    Args:
        source_id: UUID string of the source that failed
        job_id: UUID string of the failed scrape job
        error_message: Error message from the failed scrape

    Returns:
        dict: Summary of notifications sent, skipped, and failed

    Raises:
        SQLAlchemyError: If there is a database error during processing
    """
    try:
        async with AsyncSessionLocal() as session:
            source_uuid = UUID(source_id)
            job_uuid = UUID(job_id)

            # Fetch the source details
            source_result = await session.execute(
                select(Source).where(Source.id == source_uuid)
            )
            source = source_result.scalar_one_or_none()
            if not source:
                logger.warning(f"No source found with id {source_id}")
                return {"error": "Source not found"}

            # Fetch the scrape job details
            job_result = await session.execute(
                select(ScrapeJob).where(ScrapeJob.id == job_uuid)
            )
            job = job_result.scalar_one_or_none()
            if not job:
                logger.warning(f"No scrape job found with id {job_id}")
                return {"error": "Scrape job not found"}

            # Fetch jurisdiction and project
            jurisdiction_result = await session.execute(
                select(Jurisdiction).where(Jurisdiction.id == source.jurisdiction_id)
            )
            jurisdiction = jurisdiction_result.scalar_one_or_none()
            if not jurisdiction:
                logger.warning(f"No jurisdiction found for source {source_id}")
                return {"error": "Jurisdiction not found"}

            project_result = await session.execute(
                select(Project).where(Project.id == jurisdiction.project_id)
            )
            project = project_result.scalar_one_or_none()
            if not project:
                logger.warning(f"No project found for source {source_id}")
                return {"error": "Project not found"}

            # Get all users in the project
            project_users_result = await session.execute(
                select(ProjectUser).where(ProjectUser.project_id == project.id)
            )
            project_users = project_users_result.scalars().all()
            if not project_users:
                logger.info(f"No users associated with project {project.id}")
                return {"message": "No users to notify"}

            user_ids = [pu.user_id for pu in project_users]

            logger.info(
                f"Found {len(user_ids)} user(s) in project {project.id} "
                f"(organization: {getattr(project, 'organization_id', 'N/A')})"
            )

            notifications_sent = 0
            notifications_skipped = 0
            notifications_failed = 0

            notification_title = f"Scrape Job Failed: {source.name}"
            notification_message = (
                f"The scrape job for '{source.name}' has failed. "
                f"Error: {error_message[:200]}..."
                if len(error_message) > 200
                else error_message
            )
            for user_id in user_ids:
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    logger.warning(f"User {user_id} not found, skipping")
                    continue

                # Idempotency check - now using scrape_job_id for exact matching
                existing_result = await session.execute(
                    select(Notification).where(
                        Notification.scrape_job_id == job_uuid,
                        Notification.user_id == user.id,
                        Notification.notification_type
                        == NotificationType.SCRAPE_FAILED,
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    logger.info(
                        f"Scrape failure notification already exists for user {user.email} "
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
                        logger.info(
                            f"Retrying failed notification {existing.notification_id}"
                        )
                        notification = existing
                    else:
                        logger.info(
                            f"Found pending notification {existing.notification_id}, sending email"
                        )
                        notification = existing
                else:
                    notification = Notification(
                        user_id=user.id,
                        notification_type=NotificationType.SCRAPE_FAILED,
                        title=notification_title,
                        message=notification_message,
                        source_id=source.id,
                        scrape_job_id=job_uuid,  # Add the scrape job ID
                        jurisdiction_id=jurisdiction.id,
                        organization_id=getattr(project, "organization_id", None),
                        status=NotificationStatus.PENDING,
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                    session.add(notification)
                    await session.commit()
                    await session.refresh(notification)
                    logger.info(
                        f"Created scrape failure notification {notification.notification_id} "
                        f"for user {user.email}"
                    )

                email_context = {
                    "user_name": user.name or getattr(user, "username", "User"),
                    "source_name": source.name,
                    "error_message": error_message,
                    "job_id": job_id,
                    "failed_at": (
                        job.completed_at.strftime("%Y-%m-%d %H:%M:%S")
                        if job.completed_at
                        else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    ),
                    "subject": notification_title,
                    "project_name": project.name,
                    "jurisdiction_name": jurisdiction.name,
                }

                try:
                    success = await send_email(
                        template_name="scrape_failure_notification.html",
                        subject=f"Scrape Job Failed: {source.name}",
                        recipient=user.email,
                        context=email_context,
                    )
                    notification.status = (
                        NotificationStatus.SENT
                        if success
                        else NotificationStatus.FAILED
                    )
                    notification.sent_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    session.add(notification)
                    await session.commit()
                    await session.refresh(notification)

                    if success:
                        notifications_sent += 1
                        logger.info(
                            f"✓ Scrape failure notification {notification.notification_id} "
                            f"sent to {user.email}"
                        )
                    else:
                        notifications_failed += 1
                        logger.error(
                            f"✗ Failed to send scrape failure notification "
                            f"{notification.notification_id} to {user.email}"
                        )
                except Exception as e:
                    notification.status = NotificationStatus.FAILED
                    session.add(notification)
                    await session.commit()
                    notifications_failed += 1
                    logger.error(
                        f"✗ Exception sending scrape failure notification "
                        f"{notification.notification_id} to {user.email}: {str(e)}"
                    )

            summary = {
                "sent": notifications_sent,
                "skipped": notifications_skipped,
                "failed": notifications_failed,
                "source_id": source_id,
                "job_id": job_id,
            }

            logger.info(
                f"Scrape failure notification summary for source {source_id}, job {job_id}: "
                f"Sent: {notifications_sent}, "
                f"Skipped: {notifications_skipped}, Failed: {notifications_failed}"
            )

            return summary

    except SQLAlchemyError as e:
        logger.error(
            f"Database error sending scrape failure notifications for source {source_id}, "
            f"job {job_id}: {str(e)}"
        )
        raise


@shared_task(bind=True, name="send_scrape_failure_notifications", max_retries=3)
def send_scrape_failure_notifications_task(
    self, source_id: str, job_id: str, error_message: str
):
    """
    Celery task wrapper for sending scrape failure notifications to ALL project users.

    Args:
        source_id: UUID string of the source that failed
        job_id: UUID string of the failed scrape job
        error_message: Error message from the failed scrape

    Returns:
        dict: Summary of notifications sent

    Raises:
        Retries the task up to 3 times with 60 second delay on failure
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            send_scrape_failure_notifications(source_id, job_id, error_message)
        )
        logger.info(
            f"Successfully processed scrape failure notifications for source {source_id}, "
            f"job {job_id}"
        )
        return result
    except Exception as exc:
        logger.error(
            f"Error processing scrape failure notifications for source {source_id}, "
            f"job {job_id}: {str(exc)}"
        )
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()
