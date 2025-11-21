import re

from app.api.core.config import Settings

__all__ = ["is_strong_password", "is_company_email"]


def is_strong_password(password: str) -> bool:
    """Return True when a password meets strength requirements.

    The function checks for minimum length (8), presence of uppercase and
    lowercase characters, at least one digit and at least one special character.

    Args:
        password: Plaintext password to validate.

    Returns:
        True if password satisfies all checks; False otherwise.
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True


def is_company_email(email: str) -> bool:
    """Return True if the email appears to be from a company domain.

    This function checks if the email domain is not from common personal
    or disposable email providers. Can be overridden for test email providers
    via ALLOW_TEST_EMAIL_PROVIDERS configuration.

    Args:
        email: Email address to validate.

    Returns:
        True if email appears to be from a company; False otherwise.
    """
    # List of common personal/disposable email domains
    personal_domains = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "mailinator.com",
        "10minutemail.com",
        "guerrillamail.com",
        "temp-mail.org",
        "yopmail.com",
    }

    try:
        # Extract domain from email
        domain = email.split("@")[1].lower()

        # Allow test email providers if configured
        settings = Settings()
        if settings.ALLOW_TEST_EMAIL_PROVIDERS:
            test_providers = {p.strip().lower() for p in settings.TEST_EMAIL_PROVIDERS.split(",")}
            if domain in test_providers:
                return True

        return domain not in personal_domains
    except IndexError:
        # Invalid email format
        return False
