import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.api_access.models.api_key import ApiKey
from app.api.utils.key_utils import generate_raw_key, hash_key


class ApiKeyService:
    @staticmethod
    async def create_api_key(
        db: AsyncSession, organization_id: UUID, description: Optional[str] = None
    ) -> dict:
        """
        Create a new API key for an organization.

        Args:
            db (AsyncSession): Async database session.
            organization_id (UUID): Organization ID.
            description (Optional[str]): Description for the API key.

        Returns:
            dict: Contains raw API key and ApiKey model instance.
        """
        raw_key = generate_raw_key()
        key_hash = hash_key(raw_key)

        model = ApiKey(key_hash=key_hash, organization_id=organization_id, description=description)

        db.add(model)
        await db.flush()
        await db.refresh(model)

        return {"raw_key": raw_key, "api_key": model}

    @staticmethod
    async def get_api_key_by_hash(
        db: AsyncSession, key_hash: str, use_constant_time: bool = True
    ) -> Optional[ApiKey]:
        """
        Retrieve an active API key by its hash.

        Args:
            db (AsyncSession): Async database session.
            key_hash (str): Hashed API key.
            use_constant_time (bool): If True,
            use constant-time comparison for security.

        Returns:
            Optional[ApiKey]: API key instance or None if not found.
        """
        q = select(ApiKey).where(ApiKey.is_active)
        res = await db.execute(q)
        active_keys = res.scalars().all()

        if use_constant_time:
            # Compare hashes in constant-time to mitigate timing attacks
            for key in active_keys:
                if secrets.compare_digest(key.key_hash, key_hash):
                    return key
            return None

        # Fast path: exact SQL comparison (no extra defense)
        q2 = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active)
        res2 = await db.execute(q2)
        return res2.scalar_one_or_none()

    @staticmethod
    async def touch_last_used(db: AsyncSession, api_key: ApiKey) -> None:
        """
        Update the last_used_at timestamp of
        the API key without committing the transaction.
        Transaction commit should be handled externally
        to allow proper request-scoped transaction management.

        Args:
            db (AsyncSession): Async database session.
            api_key (ApiKey): API key instance.
        """
        api_key.last_used_at = datetime.now(timezone.utc)
        db.add(api_key)
