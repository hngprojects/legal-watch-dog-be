"""
Unit tests for authentication service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from app.api.modules.v1.auth.service.auth_service import AuthService
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.organization.models import Organization


class TestAuthenticateUser:
    """Tests for AuthService.authenticate_user method."""

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self):
        """Test successful user authentication with valid credentials."""
        # Create mock objects
        mock_db = AsyncMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "$2b$12$abcdef"  # Mock hashed password
        mock_user.name = "Test User"
        mock_user.is_active = True
        mock_user.organization_id = uuid.uuid4()
        
        # Mock role and organization
        mock_role = MagicMock(spec=Role)
        mock_role.name = "user"
        mock_user.role = mock_role
        
        mock_org = MagicMock(spec=Organization)
        mock_org.id = mock_user.organization_id
        mock_user.organization = mock_org

        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        # Mock password verification
        with patch('app.api.modules.v1.auth.service.auth_service.PasswordManager.verify_password', return_value=True):
            user = await AuthService.authenticate_user(
                db=mock_db,
                email="test@example.com",
                password="password123"
            )

        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self):
        """Test authentication fails with incorrect password."""
        mock_db = AsyncMock()
        mock_user = MagicMock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "$2b$12$abcdef"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        # Mock password verification to fail
        with patch('app.api.modules.v1.auth.service.auth_service.PasswordManager.verify_password', return_value=False):
            user = await AuthService.authenticate_user(
                db=mock_db,
                email="test@example.com",
                password="wrongpassword"
            )

        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self):
        """Test authentication fails when user doesn't exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        user = await AuthService.authenticate_user(
            db=mock_db,
            email="nonexistent@example.com",
            password="password123"
        )

        assert user is None


class TestLogin:
    """Tests for AuthService.login method."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login with valid credentials."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        mock_user = MagicMock(spec=User)
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.is_active = True
        mock_user.organization_id = org_id
        
        mock_role = MagicMock(spec=Role)
        mock_role.name = "user"
        mock_user.role = mock_role

        # Mock rate limiter - allow login
        with patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.check_rate_limit', 
                   return_value=(True, None)), \
             patch('app.api.modules.v1.auth.service.auth_service.AuthService.authenticate_user', 
                   return_value=mock_user), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.reset_failed_attempts'), \
             patch('app.api.modules.v1.auth.service.auth_service.JWTManager.create_access_token', 
                   return_value="access_token_123"), \
             patch('app.api.modules.v1.auth.service.auth_service.JWTManager.create_refresh_token', 
                   return_value=("refresh_token_123", "jti_123")):

            result = await AuthService.login(
                db=mock_db,
                redis_client=mock_redis,
                email="test@example.com",
                password="password123",
                client_ip="127.0.0.1"
            )

        assert result["access_token"] == "access_token_123"
        assert result["refresh_token"] == "refresh_token_123"
        assert result["token_type"] == "bearer"
        assert result["user"]["email"] == "test@example.com"
        assert result["user"]["role"] == "user"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_login_rate_limited(self):
        """Test login fails when rate limit is exceeded."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock rate limiter - deny login
        with patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.check_rate_limit', 
                   return_value=(False, 900)):
            result = await AuthService.login(
                db=mock_db,
                redis_client=mock_redis,
                email="test@example.com",
                password="password123",
                client_ip="127.0.0.1"
            )

        assert result["error"] == "RATE_LIMIT_EXCEEDED"
        assert result["status_code"] == 429
        assert result["retry_after"] == 900

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login fails with invalid credentials."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock rate limiter - allow login
        with patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.check_rate_limit', 
                   return_value=(True, None)), \
             patch('app.api.modules.v1.auth.service.auth_service.AuthService.authenticate_user', 
                   return_value=None), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.increment_failed_attempts') as mock_increment:

            result = await AuthService.login(
                db=mock_db,
                redis_client=mock_redis,
                email="test@example.com",
                password="wrongpassword",
                client_ip="127.0.0.1"
            )

        assert result["error"] == "INVALID_CREDENTIALS"
        assert result["status_code"] == 401
        mock_increment.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_inactive_account(self):
        """Test login fails when account is inactive."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        mock_user = MagicMock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.is_active = False

        # Mock rate limiter - allow login
        with patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.check_rate_limit', 
                   return_value=(True, None)), \
             patch('app.api.modules.v1.auth.service.auth_service.AuthService.authenticate_user', 
                   return_value=mock_user):

            result = await AuthService.login(
                db=mock_db,
                redis_client=mock_redis,
                email="test@example.com",
                password="password123",
                client_ip="127.0.0.1"
            )

        assert result["error"] == "ACCOUNT_INACTIVE"
        assert result["status_code"] == 403


class TestRefreshAccessToken:
    """Tests for AuthService.refresh_access_token method."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        jti = "jti_123"
        
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.organization_id = org_id
        
        mock_role = MagicMock(spec=Role)
        mock_role.name = "user"
        mock_user.role = mock_role

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        # Mock JWT verification
        mock_payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": int((datetime.now(timezone.utc)).timestamp()) + 86400,
            "type": "refresh"
        }

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=mock_payload), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.is_token_blacklisted', 
                   return_value=False), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.blacklist_token'), \
             patch('app.api.modules.v1.auth.service.auth_service.JWTManager.create_access_token', 
                   return_value="new_access_token"), \
             patch('app.api.modules.v1.auth.service.auth_service.JWTManager.create_refresh_token', 
                   return_value=("new_refresh_token", "new_jti")):

            result = await AuthService.refresh_access_token(
                db=mock_db,
                redis_client=mock_redis,
                refresh_token="old_refresh_token"
            )

        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_token(self):
        """Test refresh fails with invalid token."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=None):
            result = await AuthService.refresh_access_token(
                db=mock_db,
                redis_client=mock_redis,
                refresh_token="invalid_token"
            )

        assert result["error"] == "INVALID_TOKEN"
        assert result["status_code"] == 401

    @pytest.mark.asyncio
    async def test_refresh_token_blacklisted(self):
        """Test refresh fails when token is blacklisted."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        user_id = uuid.uuid4()
        jti = "jti_123"

        mock_payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": int((datetime.now(timezone.utc)).timestamp()) + 86400,
            "type": "refresh"
        }

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=mock_payload), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.is_token_blacklisted', 
                   return_value=True):

            result = await AuthService.refresh_access_token(
                db=mock_db,
                redis_client=mock_redis,
                refresh_token="blacklisted_token"
            )

        assert result["error"] == "INVALID_TOKEN"
        assert result["message"] == "Refresh token has been revoked"
        assert result["status_code"] == 401

    @pytest.mark.asyncio
    async def test_refresh_token_user_not_found(self):
        """Test refresh fails when user doesn't exist."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        user_id = uuid.uuid4()
        jti = "jti_123"

        mock_payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": int((datetime.now(timezone.utc)).timestamp()) + 86400,
            "type": "refresh"
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=mock_payload), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.is_token_blacklisted', 
                   return_value=False):

            result = await AuthService.refresh_access_token(
                db=mock_db,
                redis_client=mock_redis,
                refresh_token="valid_token"
            )

        assert result["error"] == "INVALID_TOKEN"
        assert result["message"] == "User not found"
        assert result["status_code"] == 401

    @pytest.mark.asyncio
    async def test_refresh_token_inactive_account(self):
        """Test refresh fails when account is inactive."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        user_id = uuid.uuid4()
        jti = "jti_123"
        
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.is_active = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        mock_payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": int((datetime.now(timezone.utc)).timestamp()) + 86400,
            "type": "refresh"
        }

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=mock_payload), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.is_token_blacklisted', 
                   return_value=False):

            result = await AuthService.refresh_access_token(
                db=mock_db,
                redis_client=mock_redis,
                refresh_token="valid_token"
            )

        assert result["error"] == "ACCOUNT_INACTIVE"
        assert result["status_code"] == 403


class TestLogout:
    """Tests for AuthService.logout method."""

    @pytest.mark.asyncio
    async def test_logout_with_refresh_token(self):
        """Test logout successfully blacklists refresh token."""
        mock_redis = AsyncMock()
        
        jti = "jti_123"
        exp = int((datetime.now(timezone.utc)).timestamp()) + 86400

        mock_payload = {
            "jti": jti,
            "exp": exp,
            "type": "refresh"
        }

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=mock_payload), \
             patch('app.api.modules.v1.auth.service.auth_service.RateLimiter.blacklist_token') as mock_blacklist:

            result = await AuthService.logout(
                redis_client=mock_redis,
                refresh_token="valid_refresh_token"
            )

        assert result["message"] == "Logged out successfully"
        assert result["status_code"] == 200
        mock_blacklist.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(self):
        """Test logout without providing refresh token."""
        mock_redis = AsyncMock()

        result = await AuthService.logout(
            redis_client=mock_redis,
            refresh_token=None
        )

        assert result["message"] == "Logged out successfully"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token(self):
        """Test logout with invalid refresh token still succeeds."""
        mock_redis = AsyncMock()

        with patch('app.api.modules.v1.auth.service.auth_service.JWTManager.verify_refresh_token', 
                   return_value=None):

            result = await AuthService.logout(
                redis_client=mock_redis,
                refresh_token="invalid_token"
            )

        assert result["message"] == "Logged out successfully"
        assert result["status_code"] == 200
