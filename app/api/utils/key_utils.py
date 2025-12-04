import secrets

import bcrypt

KEY_PREFIX = "sk_"


def generate_raw_key() -> str:
    """
    Generate a secure random API key string.

    Returns:
        str: Raw API key with prefix.
    """
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    """
    Hash the API key using bcrypt for secure storage.

    Args:
        raw_key (str): The plain API key.

    Returns:
        str: Bcrypt-hashed API key (utf-8 decoded for storage).
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(raw_key.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_key(raw_key: str, hashed_key: str) -> bool:
    """
    Verify a raw API key against the stored bcrypt hash.

    Args:
        raw_key (str): The plain API key to check.
        hashed_key (str): The stored bcrypt hash.

    Returns:
        bool: True if the key matches the hash, False otherwise.
    """
    return bcrypt.checkpw(raw_key.encode("utf-8"), hashed_key.encode("utf-8"))
