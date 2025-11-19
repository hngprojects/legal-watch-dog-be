"""Password Reset Email Function"""

import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.api.core.config import settings
from app.api.core.logger import setup_logging

setup_logging()
logger = logging.getLogger("app")


async def send_password_reset_email(context: dict):
    """
    Send password reset email with verification code.

    Args:
        context: Dictionary with:
            - user_email: Recipient email address
            - user_name: User's name
            - reset_code: 6-digit reset code
    """
    sender_email = settings.MAIL_USERNAME
    sender_display_email = settings.EMAIL
    receiver_email = context.get("user_email")
    password = settings.MAIL_PASSWORD
    port = settings.SMTP_PORT
    smtp_server = settings.SMTP_SERVER

    user_name = context.get("user_name")
    reset_code = context.get("reset_code")

    text_content = f"""Hello {user_name},

We received a request to reset your password for your Legal Watchdog account.

Your password reset code is: {reset_code}

This code will expire in 15 minutes.

For your security:
- Never share this code with anyone
- We will never ask for this code via phone or email
- This code can only be used once

If you did not request a password reset, please ignore this email.

Best regards,
The Legal Watchdog Team

---
© 2025 Legal Watchdog. All rights reserved.
This is an automated message, please do not reply to this email.
"""

    html_content = None
    try:
        template_dir = (
            Path(__file__).parent.parent / "dependencies" / "email" / "templates"
        )

        env = Environment(loader=FileSystemLoader(str(template_dir)))

        logger.info(f"Available templates: {env.list_templates()}")

        template = env.get_template("reset_password.html")

        html_content = template.render(
            subject="Password Reset Request",
            user_name=user_name,
            reset_code=reset_code,
        )

    except Exception as e:
        logger.warning(f"Could not load HTML template, using text only: {e}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Password Reset Request - Legal Watchdog"
    msg["From"] = sender_display_email
    msg["To"] = receiver_email
    logger.info(f"app password: {password}")
    logger.info(f"reset password: {reset_code}")
    msg.attach(MIMEText(text_content, "plain"))

    if html_content:
        msg.attach(MIMEText(html_content, "html"))

    await aiosmtplib.send(
        msg,
        hostname=smtp_server,
        port=port,
        username=sender_email,
        password=password,
        use_tls=True,
    )

    logger.info(f"Password reset email sent to {receiver_email}")
