"""
Unit tests for authentication routes.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import uuid

from app.api.modules.v1.auth.routes.auth_routes import router, login, refresh_token, logout
from app.api.modules.v1.users.models.users_model import User


class TestLoginRoute:
    """Tests for /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login returns tokens and user info."""
        # Mock dependencies
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        
        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "password123"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock successful login response
        mock_response = {
            "access_token": "access_token_123",
            "refresh_token": "refresh_token_123",
            "token_type": "bearer",
            "user": {
                "id": str(uuid.uuid4()),
                "email": "test@example.com",
                "name": "Test User",
                "role": "user",
                "organisation_id": str(uuid.uuid4())
            },
            "status_code": 200
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login', 
                   return_value=mock_response), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip', 
                   return_value="127.0.0.1"):
            
            result = await login(
                request=mock_request,
                login_data=mock_login_data,
                db=mock_db,
                redis_client=mock_redis
            )
        
        assert result["access_token"] == "access_token_123"
        assert result["refresh_token"] == "refresh_token_123"
        assert result["token_type"] == "bearer"
        assert result["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials raises 401."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        
        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "wrongpassword"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock failed login response
        mock_response = {
            "error": "INVALID_CREDENTIALS",
            "message": "Invalid email or password",
            "status_code": 401
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login', 
                   return_value=mock_response), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip', 
                   return_value="127.0.0.1"):
            
            with pytest.raises(HTTPException) as exc_info:
                await login(
                    request=mock_request,
                    login_data=mock_login_data,
                    db=mock_db,
                    redis_client=mock_redis
                )
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_account_inactive(self):
        """Test login with inactive account raises 403."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        
        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "password123"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock inactive account response
        mock_response = {
            "error": "ACCOUNT_INACTIVE",
            "message": "Account has been deactivated. Please contact your administrator.",
            "status_code": 403
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login', 
                   return_value=mock_response), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip', 
                   return_value="127.0.0.1"):
            
            with pytest.raises(HTTPException) as exc_info:
                await login(
                    request=mock_request,
                    login_data=mock_login_data,
                    db=mock_db,
                    redis_client=mock_redis
                )
            
            assert exc_info.value.status_code == 403
            assert exc_info.value.detail["error"] == "ACCOUNT_INACTIVE"

    @pytest.mark.asyncio
    async def test_login_rate_limited(self):
        """Test login with too many attempts raises 429."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        
        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "password123"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock rate limit response
        mock_response = {
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Too many failed login attempts. Please try again later.",
            "retry_after": 900,
            "status_code": 429
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login', 
                   return_value=mock_response), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip', 
                   return_value="127.0.0.1"):
            
            with pytest.raises(HTTPException) as exc_info:
                await login(
                    request=mock_request,
                    login_data=mock_login_data,
                    db=mock_db,
                    redis_client=mock_redis
                )
            
            assert exc_info.value.status_code == 429
            assert exc_info.value.detail["error"] == "RATE_LIMIT_EXCEEDED"
            assert exc_info.value.detail["retry_after"] == 900


class TestRefreshTokenRoute:
    """Tests for /auth/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh returns new tokens."""
        mock_refresh_data = MagicMock()
        mock_refresh_data.refresh_token = "old_refresh_token"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock successful refresh response
        mock_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "status_code": 200
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token', 
                   return_value=mock_response):
            
            result = await refresh_token(
                refresh_data=mock_refresh_data,
                db=mock_db,
                redis_client=mock_redis
            )
        
        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self):
        """Test refresh with invalid token raises 401."""
        mock_refresh_data = MagicMock()
        mock_refresh_data.refresh_token = "invalid_token"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock invalid token response
        mock_response = {
            "error": "INVALID_TOKEN",
            "message": "Refresh token is invalid or has expired",
            "status_code": 401
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token', 
                   return_value=mock_response):
            
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    refresh_data=mock_refresh_data,
                    db=mock_db,
                    redis_client=mock_redis
                )
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_refresh_token_blacklisted(self):
        """Test refresh with blacklisted token raises 401."""
        mock_refresh_data = MagicMock()
        mock_refresh_data.refresh_token = "blacklisted_token"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock blacklisted token response
        mock_response = {
            "error": "INVALID_TOKEN",
            "message": "Refresh token has been revoked",
            "status_code": 401
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token', 
                   return_value=mock_response):
            
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    refresh_data=mock_refresh_data,
                    db=mock_db,
                    redis_client=mock_redis
                )
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["message"] == "Refresh token has been revoked"

    @pytest.mark.asyncio
    async def test_refresh_token_user_inactive(self):
        """Test refresh for inactive user raises 403."""
        mock_refresh_data = MagicMock()
        mock_refresh_data.refresh_token = "valid_token"
        
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Mock inactive account response
        mock_response = {
            "error": "ACCOUNT_INACTIVE",
            "message": "Account has been deactivated",
            "status_code": 403
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token', 
                   return_value=mock_response):
            
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    refresh_data=mock_refresh_data,
                    db=mock_db,
                    redis_client=mock_redis
                )
            
            assert exc_info.value.status_code == 403


class TestLogoutRoute:
    """Tests for /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self):
        """Test successful logout."""
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        
        mock_redis = AsyncMock()
        
        # Mock successful logout response
        mock_response = {
            "message": "Logged out successfully",
            "status_code": 200
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.logout', 
                   return_value=mock_response):
            
            result = await logout(
                current_user=mock_user,
                redis_client=mock_redis,
                refresh_token="refresh_token_123"
            )
        
        assert result["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(self):
        """Test logout without providing refresh token."""
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"
        
        mock_redis = AsyncMock()
        
        # Mock successful logout response
        mock_response = {
            "message": "Logged out successfully",
            "status_code": 200
        }
        
        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.logout', 
                   return_value=mock_response):
            
            result = await logout(
                current_user=mock_user,
                redis_client=mock_redis,
                refresh_token=None
            )
        
        assert result["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_requires_authentication(self):
        """Test logout requires valid authentication."""
        # This test verifies that the get_current_user dependency is applied
        # In a real scenario, this would be tested via integration tests
        # Here we just verify the dependency is in place
        
        from inspect import signature
        sig = signature(logout)
        
        # Check that current_user parameter exists and has a dependency
        assert 'current_user' in sig.parameters
        assert sig.parameters['current_user'].default is not None


class TestRouteConfiguration:
    """Tests for route configuration and metadata."""

    def test_login_route_metadata(self):
        """Test login route has correct metadata."""
        # Find the login route
        login_route = None
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/auth/login":
                login_route = route
                break
        
        assert login_route is not None
        assert "POST" in login_route.methods

    def test_refresh_route_metadata(self):
        """Test refresh route has correct metadata."""
        # Find the refresh route
        refresh_route = None
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/auth/refresh":
                refresh_route = route
                break
        
        assert refresh_route is not None
        assert "POST" in refresh_route.methods

    def test_logout_route_metadata(self):
        """Test logout route has correct metadata."""
        # Find the logout route
        logout_route = None
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "/auth/logout":
                logout_route = route
                break
        
        assert logout_route is not None
        assert "POST" in logout_route.methods

    def test_router_prefix(self):
        """Test router has correct prefix."""
        assert router.prefix == "/auth"

    def test_router_tags(self):
        """Test router has correct tags."""
        assert "Authentication" in router.tags
