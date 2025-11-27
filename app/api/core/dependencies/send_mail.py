import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

import aiosmtplib

from app.api.core.config import settings

logger = logging.getLogger("app")


async def send_email(
    template_name: str, subject: str, recipient: str, context: Dict[str, Any]
) -> bool:
    from main import email_templates

    try:
        sender_email = settings.MAIL_USERNAME
        sender_display_email = settings.EMAIL
        password = settings.MAIL_PASSWORD
        port = settings.SMTP_PORT
        smtp_server = settings.SMTP_SERVER

        if not recipient or recipient == "None":
            logger.error(f"Invalid recipient email: {recipient}")
            return False

        template = email_templates.get_template(template_name)
        html_content = template.render(**context)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_display_email
        msg["To"] = recipient

        msg.attach(MIMEText(html_content, "html"))

        await aiosmtplib.send(
            msg,
            hostname=smtp_server,
            port=port,
            username=sender_email,
            password=password,
            start_tls=True,
        )

        logger.info(f"Email sent successfully to {recipient}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {str(e)}", exc_info=True)
        return False
