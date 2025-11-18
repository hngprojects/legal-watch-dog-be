"""
Redis client configuration and utilities.
"""
from typing import Optional
import redis.asyncio as redis
from app.api.core.config import settings


class RedisClient:
    """
    Singleton Redis client for async operations.
    """
    _instance: Optional[redis.Redis] = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        """
        Get or create Redis client instance.
        
        Returns:
            redis.Redis: Async Redis client instance.
        """
        if cls._instance is None:
            if settings.REDIS_URL:
                cls._instance = await redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
            else:
                cls._instance = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                    encoding="utf-8",
                    decode_responses=True
                )
        return cls._instance

    @classmethod
    async def close(cls):
        """
        Close Redis client connection.
        """
        if cls._instance:
            await cls._instance.close()
            cls._instance = None


async def get_redis() -> redis.Redis:
    """
    Dependency to get Redis client.
    
    Returns:
        redis.Redis: Async Redis client instance.
    """
    return await RedisClient.get_client()
