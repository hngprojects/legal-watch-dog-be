import logging
import re

from app.api.utils.email_verifier import BusinessEmailVerifier, EmailType

logger = logging.getLogger(__name__)


def is_company_email(email: str) -> bool:
    """Return True if an email appears to be from a business/enterprise.

    This function is a small wrapper around :class:`BusinessEmailVerifier`
    used by registration to block free and disposable addresses.

    Args:
        email: The email address to check.

    Returns:
        True if the email is classified as `EmailType.BUSINESS` or `EmailType.ROLE_BASED`
        and not disposable.
    """
    verifier = BusinessEmailVerifier()
    result = verifier.verify_email(email)
    return result.email_type in (EmailType.BUSINESS, EmailType.ROLE_BASED) and result.is_valid


def is_strong_password(password: str) -> bool:
    """Validate password strength using simple heuristics.

    The check verifies the password length and the presence of at least one
    uppercase character, lowercase character, number, and special symbol.

    Args:
        password: The plaintext password to check.

    Returns:
        True when requirements are satisfied, False otherwise.
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
