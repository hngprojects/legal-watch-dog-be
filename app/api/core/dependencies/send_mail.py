import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.api.core.config import settings

async def send_email(context: dict):       
    sender_email = settings.MAIL_USERNAME
    sender_display_email = settings.EMAIL
    receiver_email = context.get('organization_email')
    password = settings.MAIL_PASSWORD
    port = settings.SMTP_PORT
    smtp_server = settings.SMTP_SERVER

    org_name = context.get('organization_name')
    
    text_content = f"""Good day {org_name} team,

Thanks for joining the Legal Watchdog Waitlist! We're thrilled to have you on board.
"""
    
    text_content += f"\nWe've registered {org_name} and we'll keep you updated on our launch.\n"
    
    text_content += """
You're now part of an exclusive group that will get:
- Early access when we launch
- Special founder pricing
- Priority support

We'll notify you as soon as we're ready to go live!

Best regards,
The Legal Watchdog Team

---
© 2025 Legal Watchdog. All rights reserved.
You're receiving this because you signed up for our waitlist.
"""

    msg = MIMEMultipart()
    msg['Subject'] = "You're on the Waitlist for Legal Watchdog!"
    msg['From'] = sender_display_email
    msg['To'] = receiver_email
    msg.attach(MIMEText(text_content, 'plain'))

    # Use aiosmtplib for true async email sending
    await aiosmtplib.send(
        msg,
        hostname=smtp_server,
        port=port,
        username=sender_email,
        password=password,
        start_tls=True
    )