"""
Rate limiting service using Redis.
"""
from typing import Optional
import redis.asyncio as redis
from datetime import timedelta


class RateLimiter:
    """
    Rate limiting utilities for authentication endpoints.
    """

    # Rate limit constants
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15

    @staticmethod
    def _get_login_key(identifier: str) -> str:
        """
        Get Redis key for login attempts.

        Args:
            identifier: Email or IP address

        Returns:
            str: Redis key
        """
        return f"login_attempts:{identifier}"

    @staticmethod
    async def check_rate_limit(redis_client: redis.Redis, identifier: str) -> tuple[bool, Optional[int]]:
        """
        Check if login attempts exceed rate limit.

        Args:
            redis_client: Redis client instance
            identifier: Email or IP address to check

        Returns:
            tuple: (is_allowed, retry_after_seconds)
                - is_allowed: True if under limit, False if locked out
                - retry_after_seconds: None if allowed, seconds remaining if locked
        """
        key = RateLimiter._get_login_key(identifier)
        attempts = await redis_client.get(key)

        if attempts is None:
            return True, None

        attempts = int(attempts)
        if attempts >= RateLimiter.MAX_LOGIN_ATTEMPTS:
            ttl = await redis_client.ttl(key)
            return False, ttl if ttl > 0 else 900  # Default 15 minutes

        return True, None

    @staticmethod
    async def increment_failed_attempts(redis_client: redis.Redis, identifier: str) -> int:
        """
        Increment failed login attempts counter.

        Args:
            redis_client: Redis client instance
            identifier: Email or IP address

        Returns:
            int: Current number of attempts
        """
        key = RateLimiter._get_login_key(identifier)
        attempts = await redis_client.incr(key)

        if attempts == 1:
            # Set expiry on first attempt
            await redis_client.expire(key, timedelta(minutes=RateLimiter.LOGIN_LOCKOUT_MINUTES))

        return attempts

    @staticmethod
    async def reset_failed_attempts(redis_client: redis.Redis, identifier: str):
        """
        Reset failed login attempts counter.

        Args:
            redis_client: Redis client instance
            identifier: Email or IP address
        """
        key = RateLimiter._get_login_key(identifier)
        await redis_client.delete(key)

    @staticmethod
    async def is_token_blacklisted(redis_client: redis.Redis, jti: str) -> bool:
        """
        Check if refresh token JTI is blacklisted.

        Args:
            redis_client: Redis client instance
            jti: JWT ID (JTI) from refresh token

        Returns:
            bool: True if blacklisted, False otherwise
        """
        key = f"blacklist:{jti}"
        return await redis_client.exists(key) > 0

    @staticmethod
    async def blacklist_token(redis_client: redis.Redis, jti: str, ttl_seconds: int):
        """
        Blacklist a refresh token by its JTI.

        Args:
            redis_client: Redis client instance
            jti: JWT ID (JTI) to blacklist
            ttl_seconds: Time to live in seconds (should match token expiry)
        """
        key = f"blacklist:{jti}"
        await redis_client.setex(key, ttl_seconds, "1")
