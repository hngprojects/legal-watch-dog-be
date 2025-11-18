"""
Unit tests for authentication routes.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status, Response
from fastapi.testclient import TestClient
import uuid

from app.api.modules.v1.auth.routes.auth_routes import router, login, refresh_token, logout
from app.api.modules.v1.users.models.users_model import User


class TestLoginRoute:
    """Tests for /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login sets HttpOnly cookies and returns user info."""
        # Mock dependencies
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_response = Response()

        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "password123"

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock successful login response
        mock_response_data = {
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
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip',
                   return_value="127.0.0.1"), \
             patch('app.api.modules.v1.auth.routes.auth_routes.settings') as mock_settings:

            # Mock settings
            mock_settings.COOKIE_NAME_ACCESS = "access_token"
            mock_settings.COOKIE_NAME_REFRESH = "refresh_token"
            mock_settings.COOKIE_SECURE = False
            mock_settings.COOKIE_SAMESITE = "lax"
            mock_settings.COOKIE_DOMAIN = None
            mock_settings.COOKIE_MAX_AGE_ACCESS = 3600
            mock_settings.COOKIE_MAX_AGE_REFRESH = 2592000

            result = await login(
                request=mock_request,
                response=mock_response,
                login_data=mock_login_data,
                db=mock_db,
                redis_client=mock_redis
            )

        # Check response structure (no tokens in body)
        assert result["message"] == "Login successful"
        assert result["user"]["email"] == "test@example.com"
        assert "access_token" not in result
        assert "refresh_token" not in result

        # Check that cookies were set (FastAPI sets multiple cookies as separate headers)
        cookie_headers = mock_response.headers.getlist("set-cookie")
        assert len(cookie_headers) >= 2  # Should have at least access and refresh cookies
        
        # Check access token cookie
        access_cookie = next((h for h in cookie_headers if "access_token=" in h), None)
        assert access_cookie is not None
        assert "access_token_123" in access_cookie
        assert "HttpOnly" in access_cookie
        
        # Check refresh token cookie
        refresh_cookie = next((h for h in cookie_headers if "refresh_token=" in h), None)
        assert refresh_cookie is not None
        assert "refresh_token_123" in refresh_cookie
        assert "HttpOnly" in refresh_cookie

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials raises 401."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_response = Response()

        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "wrongpassword"

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock failed login response
        mock_response_data = {
            "error": "INVALID_CREDENTIALS",
            "message": "Invalid email or password",
            "status_code": 401
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login',
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip',
                   return_value="127.0.0.1"):

            with pytest.raises(HTTPException) as exc_info:
                await login(
                    request=mock_request,
                    response=mock_response,
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

        mock_response = Response()

        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "password123"

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock inactive account response
        mock_response_data = {
            "error": "ACCOUNT_INACTIVE",
            "message": "Account has been deactivated. Please contact your administrator.",
            "status_code": 403
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login',
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip',
                   return_value="127.0.0.1"):

            with pytest.raises(HTTPException) as exc_info:
                await login(
                    request=mock_request,
                    response=mock_response,
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

        mock_response = Response()

        mock_login_data = MagicMock()
        mock_login_data.email = "test@example.com"
        mock_login_data.password = "password123"

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock rate limit response
        mock_response_data = {
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Too many failed login attempts. Please try again later.",
            "retry_after": 900,
            "status_code": 429
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.login',
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.get_client_ip',
                   return_value="127.0.0.1"):

            with pytest.raises(HTTPException) as exc_info:
                await login(
                    request=mock_request,
                    response=mock_response,
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
        """Test successful token refresh sets new HttpOnly cookies."""
        mock_request = MagicMock()
        mock_request.cookies = {"refresh_token": "old_refresh_token"}

        mock_response = Response()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock successful refresh response
        mock_response_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "status_code": 200
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token',
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.settings') as mock_settings:

            # Mock settings
            mock_settings.COOKIE_NAME_ACCESS = "access_token"
            mock_settings.COOKIE_NAME_REFRESH = "refresh_token"
            mock_settings.COOKIE_SECURE = False
            mock_settings.COOKIE_SAMESITE = "lax"
            mock_settings.COOKIE_DOMAIN = None
            mock_settings.COOKIE_MAX_AGE_ACCESS = 3600
            mock_settings.COOKIE_MAX_AGE_REFRESH = 2592000

            result = await refresh_token(
                request=mock_request,
                response=mock_response,
                db=mock_db,
                redis_client=mock_redis
            )

        # Check response structure (no tokens in body)
        assert result["message"] == "Token refreshed successfully"
        assert "access_token" not in result
        assert "refresh_token" not in result

        # Check that new cookies were set (FastAPI sets multiple cookies as separate headers)
        cookie_headers = mock_response.headers.getlist("set-cookie")
        assert len(cookie_headers) >= 2  # Should have at least access and refresh cookies
        
        # Check access token cookie
        access_cookie = next((h for h in cookie_headers if "access_token=" in h), None)
        assert access_cookie is not None
        assert "new_access_token" in access_cookie
        assert "HttpOnly" in access_cookie
        
        # Check refresh token cookie
        refresh_cookie = next((h for h in cookie_headers if "refresh_token=" in h), None)
        assert refresh_cookie is not None
        assert "new_refresh_token" in refresh_cookie
        assert "HttpOnly" in refresh_cookie

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self):
        """Test refresh with invalid token raises 401."""
        mock_request = MagicMock()
        mock_request.cookies = {"refresh_token": "invalid_token"}

        mock_response = Response()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock invalid token response
        mock_response_data = {
            "error": "INVALID_TOKEN",
            "message": "Refresh token is invalid or has expired",
            "status_code": 401
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token',
                   return_value=mock_response_data):

            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    request=mock_request,
                    response=mock_response,
                    db=mock_db,
                    redis_client=mock_redis
                )

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_refresh_token_blacklisted(self):
        """Test refresh with blacklisted token raises 401."""
        mock_request = MagicMock()
        mock_request.cookies = {"refresh_token": "blacklisted_token"}

        mock_response = Response()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock blacklisted token response
        mock_response_data = {
            "error": "INVALID_TOKEN",
            "message": "Refresh token has been revoked",
            "status_code": 401
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token',
                   return_value=mock_response_data):

            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    request=mock_request,
                    response=mock_response,
                    db=mock_db,
                    redis_client=mock_redis
                )

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["message"] == "Refresh token has been revoked"

    @pytest.mark.asyncio
    async def test_refresh_token_user_inactive(self):
        """Test refresh for inactive user raises 403."""
        mock_request = MagicMock()
        mock_request.cookies = {"refresh_token": "valid_token"}

        mock_response = Response()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock inactive account response
        mock_response_data = {
            "error": "ACCOUNT_INACTIVE",
            "message": "Account has been deactivated",
            "status_code": 403
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.refresh_access_token',
                   return_value=mock_response_data):

            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    request=mock_request,
                    response=mock_response,
                    db=mock_db,
                    redis_client=mock_redis
                )

            assert exc_info.value.status_code == 403


class TestLogoutRoute:
    """Tests for /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self):
        """Test successful logout clears HttpOnly cookies."""
        mock_request = MagicMock()
        mock_request.cookies = {"refresh_token": "refresh_token_123"}

        mock_response = Response()

        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"

        mock_redis = AsyncMock()

        # Mock successful logout response
        mock_response_data = {
            "message": "Logged out successfully",
            "status_code": 200
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.logout',
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.settings') as mock_settings:

            # Mock settings
            mock_settings.COOKIE_NAME_ACCESS = "access_token"
            mock_settings.COOKIE_NAME_REFRESH = "refresh_token"
            mock_settings.COOKIE_DOMAIN = None
            mock_settings.COOKIE_SECURE = False
            mock_settings.COOKIE_SAMESITE = "lax"

            result = await logout(
                request=mock_request,
                response=mock_response,
                current_user=mock_user,
                redis_client=mock_redis
            )

        # Check that cookies were cleared (FastAPI sets multiple cookies as separate headers)
        cookie_headers = mock_response.headers.getlist("set-cookie")
        assert len(cookie_headers) >= 2  # Should have at least access and refresh cookies
        
        # Check access token cookie is cleared
        access_cookie = next((h for h in cookie_headers if "access_token=" in h), None)
        assert access_cookie is not None
        assert "access_token=\"\"" in access_cookie  # Empty value
        assert "Max-Age=0" in access_cookie
        
        # Check refresh token cookie is cleared
        refresh_cookie = next((h for h in cookie_headers if "refresh_token=" in h), None)
        assert refresh_cookie is not None
        assert "refresh_token=\"\"" in refresh_cookie  # Empty value
        assert "Max-Age=0" in refresh_cookie

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(self):
        """Test logout without refresh token in cookies."""
        mock_request = MagicMock()
        mock_request.cookies = {}  # No refresh token cookie

        mock_response = Response()

        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@example.com"

        mock_redis = AsyncMock()

        # Mock successful logout response
        mock_response_data = {
            "message": "Logged out successfully",
            "status_code": 200
        }

        with patch('app.api.modules.v1.auth.routes.auth_routes.AuthService.logout',
                   return_value=mock_response_data), \
             patch('app.api.modules.v1.auth.routes.auth_routes.settings') as mock_settings:

            # Mock settings
            mock_settings.COOKIE_NAME_ACCESS = "access_token"
            mock_settings.COOKIE_NAME_REFRESH = "refresh_token"
            mock_settings.COOKIE_DOMAIN = None
            mock_settings.COOKIE_SECURE = False
            mock_settings.COOKIE_SAMESITE = "lax"

            result = await logout(
                request=mock_request,
                response=mock_response,
                current_user=mock_user,
                redis_client=mock_redis
            )

        assert result["message"] == "Logged out successfully"

        # Check that cookies were cleared
        assert mock_response.headers.get("set-cookie") is not None

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
