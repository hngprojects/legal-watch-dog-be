import logging

from app.api.core.dependencies.send_mail import send_email
from app.api.core.logger import setup_logging

setup_logging()
logger = logging.getLogger("app")


async def send_password_reset_email(context: dict):
    """
    Send password reset email using the shared send_email utility.

    Args:
        context: Dictionary with:
            - user_email: Recipient email address
            - user_name: User's name
            - reset_code: 6-digit reset code
    """

    recipient = context.get("user_email")
    user_name = context.get("user_name")
    reset_code = context.get("reset_code")

    subject = "Password Reset Request - Legal Watchdog"

    template_name = "reset_password.html"

    template_context = {
        "subject": subject,
        "user_name": user_name,
        "reset_code": reset_code,
    }

    logger.info(f"Attempting to send password reset email to {recipient}")

    success = await send_email(
        template_name=template_name,
        subject=subject,
        recipient=recipient,
        context=template_context,
    )

    if success:
        logger.info(f"Password reset email successfully sent to {recipient}")
    else:
        logger.error(f"Failed to send password reset email to {recipient}")

    return success
