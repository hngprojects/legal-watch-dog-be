# app/api/modules/v1/integrations/services/api_key_service.py
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.api_access.models.api_key import ApiKey
from app.api.utils.key_utils import generate_raw_key, hash_key


class ApiKeyService:
    @staticmethod
    async def create_api_key(db: AsyncSession, organization_id, description=None):
        raw_key = generate_raw_key()
        key_hash = hash_key(raw_key)

        model = ApiKey(key_hash=key_hash, organization_id=organization_id, description=description)

        db.add(model)
        await db.flush()
        await db.refresh(model)

        return {"raw_key": raw_key, "api_key": model}

    @staticmethod
    async def get_api_key_by_hash(db: AsyncSession, key_hash: str):
        q = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active)
        res = await db.execute(q)
        return res.scalar_one_or_none()

    @staticmethod
    async def touch_last_used(db: AsyncSession, api_key: ApiKey):
        api_key.last_used_at = datetime.now(timezone.utc)
        db.add(api_key)
        await db.commit()
