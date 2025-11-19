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


def is_strong_password(password: str) -> bool:
    """Check if password meets industry standard requirements."""
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
