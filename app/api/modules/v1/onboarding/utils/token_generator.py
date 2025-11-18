import secrets
import hashlib
import hmac

from app.api.core.config import settings


def make_token(nbytes: int = 32) -> str:
    """Generate a URL-safe random token string."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Return an HMAC-SHA256 hex digest of the token using SECRET_KEY."""
    key = (settings.SECRET_KEY or "").encode("utf-8")
    return hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_token(provided_token: str, stored_hash: str) -> bool:
    """Verify a provided token against the stored hash in constant time."""
    return hmac.compare_digest(hash_token(provided_token), stored_hash)
