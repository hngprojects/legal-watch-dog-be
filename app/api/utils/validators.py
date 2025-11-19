import re

# List of common public email domains to block
PUBLIC_EMAIL_DENYLIST = {
    # "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "icloud.com",
    "mail.com",
    "protonmail.com",
    "zoho.com",
    "gmx.com",
    "yandex.com",
    "msn.com",
    "live.com",
    "ymail.com",
    "inbox.com",
    "me.com",
    "fastmail.com",
    "hushmail.com",
}


def is_company_email(email: str) -> bool:
    """Return True if email is not from a public provider."""
    domain = email.split("@")[-1].lower()
    return domain not in PUBLIC_EMAIL_DENYLIST


def is_strong_password(password: str) -> str:
    """
    Check if password meets industry standard requirements.
    
    Returns an error message if validation fails, otherwise an empty string.
    """
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("one special character (!@#$%^&*(),.?\":{}|<>)")
    if errors:
        return (
            "Password must contain: " + ", ".join(errors) + "."
        )
    return ""
