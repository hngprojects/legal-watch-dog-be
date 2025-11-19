import re

__all__ = ["is_strong_password"]


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
