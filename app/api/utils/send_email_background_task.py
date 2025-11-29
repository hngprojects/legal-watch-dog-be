import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict

from app.api.core.config import settings
from app.api.core.logger import logger
from app.api.utils.email_verifier import BusinessEmailVerifier
from app.api.utils.template_utils import render_template
from app.celery_app import celery_app

# Email verifier instance
email_verifier = BusinessEmailVerifier()


@celery_app.task(bind=True, name="send_email_background_task")
def send_email_background_task(
    self,
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, str],
):
    """
    Send an email asynchronously using Celery.
    Validates the email before sending.
    """
    try:
        # Validate email
        verification_result = email_verifier.verify_email(to_email)
        if not verification_result.is_valid:
            logger.warning(
                f"Email verification failed for {to_email}. Skipping send.",
                extra={"email": to_email, "error": verification_result.error_message},
            )
            return

        # Render HTML email using template_utils
        html_content = render_template(f"{template_name}.html", context)

        # Compose email
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        # Send email
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            # Use TLS if port indicates STARTTLS
            if settings.SMTP_PORT in [587, 465]:
                server.starttls()
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.EMAIL, to_email, msg.as_string())

        logger.info(
            f"Email sent successfully to {to_email}",
            extra={"email": to_email, "template": template_name},
        )

    except smtplib.SMTPException as e:
        logger.error(
            f"SMTP error while sending email to {to_email}: {str(e)}",
            exc_info=True,
            extra={"email": to_email, "template": template_name},
        )
        # Retry on SMTP errors
        raise self.retry(exc=e, countdown=60, max_retries=3)

    except Exception as e:
        logger.error(
            f"Failed to send email to {to_email}: {str(e)}",
            exc_info=True,
            extra={"email": to_email, "template": template_name},
        )
        raise self.retry(exc=e, countdown=60, max_retries=3)
