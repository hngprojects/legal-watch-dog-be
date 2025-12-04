# app/api/utils/api_key_auth.py
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.api_access.service.api_key_service import ApiKeyService
from app.api.utils.key_utils import hash_key


async def require_api_key(x_api_key: str = Header(None), db: AsyncSession = Depends(get_db)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_key(x_api_key)
    api_key = await ApiKeyService.get_api_key_by_hash(db, key_hash)

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # expiry check
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")

    await ApiKeyService.touch_last_used(db, api_key)

    # Return organization scope
    return api_key
