"""
Unit tests for rate limiter service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta

from app.api.modules.v1.auth.service.rate_limiter import RateLimiter


class TestCheckRateLimit:
    """Tests for RateLimiter.check_rate_limit method."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_attempts(self):
        """Test rate limit check when there are no previous attempts."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        
        is_allowed, retry_after = await RateLimiter.check_rate_limit(
            mock_redis, 
            "test@example.com"
        )
        
        assert is_allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_under_limit(self):
        """Test rate limit check when attempts are under the limit."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "3"  # 3 attempts, under MAX_LOGIN_ATTEMPTS (5)
        
        is_allowed, retry_after = await RateLimiter.check_rate_limit(
            mock_redis, 
            "test@example.com"
        )
        
        assert is_allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_at_limit(self):
        """Test rate limit check when attempts are at the limit."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "5"  # At MAX_LOGIN_ATTEMPTS (5)
        mock_redis.ttl.return_value = 600  # 10 minutes remaining
        
        is_allowed, retry_after = await RateLimiter.check_rate_limit(
            mock_redis, 
            "test@example.com"
        )
        
        assert is_allowed is False
        assert retry_after == 600

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self):
        """Test rate limit check when attempts exceed the limit."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "10"  # Exceeds MAX_LOGIN_ATTEMPTS (5)
        mock_redis.ttl.return_value = 300  # 5 minutes remaining
        
        is_allowed, retry_after = await RateLimiter.check_rate_limit(
            mock_redis, 
            "test@example.com"
        )
        
        assert is_allowed is False
        assert retry_after == 300

    @pytest.mark.asyncio
    async def test_check_rate_limit_ttl_expired(self):
        """Test rate limit check when TTL returns -1 (key exists but no TTL)."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "6"
        mock_redis.ttl.return_value = -1  # No TTL set
        
        is_allowed, retry_after = await RateLimiter.check_rate_limit(
            mock_redis, 
            "test@example.com"
        )
        
        assert is_allowed is False
        assert retry_after == 900  # Default 15 minutes


class TestIncrementFailedAttempts:
    """Tests for RateLimiter.increment_failed_attempts method."""

    @pytest.mark.asyncio
    async def test_increment_first_attempt(self):
        """Test incrementing on first failed attempt sets expiry."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1  # First attempt
        
        attempts = await RateLimiter.increment_failed_attempts(
            mock_redis, 
            "test@example.com"
        )
        
        assert attempts == 1
        mock_redis.incr.assert_called_once_with("login_attempts:test@example.com")
        mock_redis.expire.assert_called_once()
        
        # Verify expire was called with correct timedelta
        call_args = mock_redis.expire.call_args
        assert call_args[0][0] == "login_attempts:test@example.com"
        assert isinstance(call_args[0][1], timedelta)

    @pytest.mark.asyncio
    async def test_increment_subsequent_attempt(self):
        """Test incrementing on subsequent failed attempt."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 3  # Third attempt
        
        attempts = await RateLimiter.increment_failed_attempts(
            mock_redis, 
            "test@example.com"
        )
        
        assert attempts == 3
        mock_redis.incr.assert_called_once()
        # Expire should not be called for subsequent attempts
        mock_redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_increment_uses_correct_key_format(self):
        """Test that increment uses correct Redis key format."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        
        await RateLimiter.increment_failed_attempts(
            mock_redis, 
            "user@example.com"
        )
        
        mock_redis.incr.assert_called_with("login_attempts:user@example.com")


class TestResetFailedAttempts:
    """Tests for RateLimiter.reset_failed_attempts method."""

    @pytest.mark.asyncio
    async def test_reset_failed_attempts(self):
        """Test resetting failed attempts deletes the key."""
        mock_redis = AsyncMock()
        
        await RateLimiter.reset_failed_attempts(
            mock_redis, 
            "test@example.com"
        )
        
        mock_redis.delete.assert_called_once_with("login_attempts:test@example.com")

    @pytest.mark.asyncio
    async def test_reset_uses_correct_key_format(self):
        """Test that reset uses correct Redis key format."""
        mock_redis = AsyncMock()
        
        await RateLimiter.reset_failed_attempts(
            mock_redis, 
            "another@example.com"
        )
        
        mock_redis.delete.assert_called_with("login_attempts:another@example.com")


class TestIsTokenBlacklisted:
    """Tests for RateLimiter.is_token_blacklisted method."""

    @pytest.mark.asyncio
    async def test_token_not_blacklisted(self):
        """Test checking a token that is not blacklisted."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0  # Key doesn't exist
        
        is_blacklisted = await RateLimiter.is_token_blacklisted(
            mock_redis, 
            "jti_123"
        )
        
        assert is_blacklisted is False
        mock_redis.exists.assert_called_once_with("blacklist:jti_123")

    @pytest.mark.asyncio
    async def test_token_is_blacklisted(self):
        """Test checking a token that is blacklisted."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1  # Key exists
        
        is_blacklisted = await RateLimiter.is_token_blacklisted(
            mock_redis, 
            "jti_456"
        )
        
        assert is_blacklisted is True
        mock_redis.exists.assert_called_once_with("blacklist:jti_456")

    @pytest.mark.asyncio
    async def test_token_blacklist_key_format(self):
        """Test that blacklist check uses correct Redis key format."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        
        await RateLimiter.is_token_blacklisted(
            mock_redis, 
            "unique_jti_789"
        )
        
        mock_redis.exists.assert_called_with("blacklist:unique_jti_789")


class TestBlacklistToken:
    """Tests for RateLimiter.blacklist_token method."""

    @pytest.mark.asyncio
    async def test_blacklist_token(self):
        """Test blacklisting a token with TTL."""
        mock_redis = AsyncMock()
        
        await RateLimiter.blacklist_token(
            mock_redis, 
            "jti_123", 
            3600  # 1 hour
        )
        
        mock_redis.setex.assert_called_once_with(
            "blacklist:jti_123", 
            3600, 
            "1"
        )

    @pytest.mark.asyncio
    async def test_blacklist_token_different_ttl(self):
        """Test blacklisting token with different TTL values."""
        mock_redis = AsyncMock()
        
        # Test with 30 days (2592000 seconds)
        await RateLimiter.blacklist_token(
            mock_redis, 
            "jti_long_lived", 
            2592000
        )
        
        mock_redis.setex.assert_called_with(
            "blacklist:jti_long_lived", 
            2592000, 
            "1"
        )

    @pytest.mark.asyncio
    async def test_blacklist_token_key_format(self):
        """Test that blacklist uses correct Redis key format."""
        mock_redis = AsyncMock()
        
        await RateLimiter.blacklist_token(
            mock_redis, 
            "test_jti", 
            1800
        )
        
        mock_redis.setex.assert_called_with(
            "blacklist:test_jti", 
            1800, 
            "1"
        )


class TestRateLimiterConstants:
    """Tests for RateLimiter class constants."""

    def test_max_login_attempts(self):
        """Test MAX_LOGIN_ATTEMPTS constant value."""
        assert RateLimiter.MAX_LOGIN_ATTEMPTS == 5

    def test_login_lockout_minutes(self):
        """Test LOGIN_LOCKOUT_MINUTES constant value."""
        assert RateLimiter.LOGIN_LOCKOUT_MINUTES == 15


class TestGetLoginKey:
    """Tests for RateLimiter._get_login_key private method."""

    def test_get_login_key_format(self):
        """Test login key format generation."""
        key = RateLimiter._get_login_key("test@example.com")
        assert key == "login_attempts:test@example.com"

    def test_get_login_key_with_ip(self):
        """Test login key format with IP address."""
        key = RateLimiter._get_login_key("192.168.1.1")
        assert key == "login_attempts:192.168.1.1"

    def test_get_login_key_consistency(self):
        """Test that same identifier produces same key."""
        identifier = "user@domain.com"
        key1 = RateLimiter._get_login_key(identifier)
        key2 = RateLimiter._get_login_key(identifier)
        assert key1 == key2


class TestRateLimiterIntegration:
    """Integration tests for multiple rate limiter operations."""

    @pytest.mark.asyncio
    async def test_full_rate_limit_flow(self):
        """Test complete rate limiting flow: increment, check, reset."""
        mock_redis = AsyncMock()
        identifier = "test@example.com"
        
        # Simulate incrementing to max attempts
        mock_redis.incr.side_effect = [1, 2, 3, 4, 5]
        
        for i in range(5):
            await RateLimiter.increment_failed_attempts(mock_redis, identifier)
        
        # Check that we're now rate limited
        mock_redis.get.return_value = "5"
        mock_redis.ttl.return_value = 900
        
        is_allowed, retry_after = await RateLimiter.check_rate_limit(
            mock_redis, 
            identifier
        )
        
        assert is_allowed is False
        assert retry_after == 900
        
        # Reset and verify we can try again
        await RateLimiter.reset_failed_attempts(mock_redis, identifier)
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_token_blacklist_flow(self):
        """Test complete token blacklist flow: blacklist, check."""
        mock_redis = AsyncMock()
        jti = "test_jti_xyz"
        ttl = 3600
        
        # Blacklist the token
        await RateLimiter.blacklist_token(mock_redis, jti, ttl)
        mock_redis.setex.assert_called_once()
        
        # Check if it's blacklisted
        mock_redis.exists.return_value = 1
        is_blacklisted = await RateLimiter.is_token_blacklisted(mock_redis, jti)
        
        assert is_blacklisted is True
