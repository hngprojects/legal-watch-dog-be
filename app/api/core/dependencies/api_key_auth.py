from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.api_access.models.api_key import ApiKey
from app.api.modules.v1.api_access.service.api_key_service import ApiKeyService
from app.api.utils.key_utils import hash_key


async def require_api_key(
    x_api_key: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)
) -> ApiKey:
    """
    Validate and return an API key instance from the request header.

    This dependency checks if the provided API key exists, is active, and
    has not expired. It also updates the `last_used_at` timestamp if more
    than 1 hour has passed since last usage.

    Args:
        x_api_key (Optional[str]): API key provided in the request header.
        db (AsyncSession): Asynchronous SQLAlchemy session dependency.

    Raises:
        HTTPException: If the API key is missing, invalid, or expired.

    Returns:
        ApiKey: The validated API key instance, including organization scope.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_key(x_api_key)
    api_key = await ApiKeyService.get_api_key_by_hash(db, key_hash)

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check expiry
    now = datetime.now(timezone.utc)
    if api_key.expires_at and api_key.expires_at < now:
        raise HTTPException(status_code=401, detail="API key expired")

    # Update last_used_at if first use or >1 hour since last use
    if not api_key.last_used_at or (now - api_key.last_used_at).total_seconds() > 3600:
        await ApiKeyService.touch_last_used(db, api_key)

    return api_key
