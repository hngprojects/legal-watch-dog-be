import base64
import logging
import os
from datetime import timedelta
from typing import Optional, Tuple

import msal
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.modules.v1.auth.schemas.oauth_microsoft import MicrosoftUserInfo
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import create_access_token
from app.api.utils.password import hash_password

logger = logging.getLogger(__name__)

MICROSOFT_SCOPES: list[str] = settings.MICROSOFT_SCOPES
MICROSOFT_OAUTH_STATE_TTL: int = settings.MICROSOFT_OAUTH_STATE_TTL


class MicrosoftOAuthService:
    """Service for handling Microsoft OAuth authentication using MSAL."""

    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client

        self.msal_app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        )

    async def generate_authorization_url(
        self, redirect_uri: Optional[str] = None
    ) -> Tuple[str, str]:
        """Generate Microsoft OAuth authorization URL."""
        state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("utf-8")

        await self.redis_client.setex(
            f"microsoft_oauth_state:{state}", MICROSOFT_OAUTH_STATE_TTL, "pending"
        )

        redirect = redirect_uri or settings.MICROSOFT_REDIRECT_URI

        from urllib.parse import urlencode

        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect,
            "response_mode": "query",
            "scope": " ".join(MICROSOFT_SCOPES),
            "state": state,
            "prompt": "select_account",
        }

        base_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
        auth_url = f"{base_url}?{urlencode(params)}"

        logger.info("Generated Microsoft auth URL")
        return auth_url, state

    async def validate_state(self, state: str) -> bool:
        """Validate OAuth state parameter against Redis storage."""
        redis_state = await self.redis_client.get(f"microsoft_oauth_state:{state}")
        if redis_state:
            return True
        logger.warning("Invalid or expired OAuth state: %s", state)
        return False

    async def exchange_code_for_token(
        self, code: str, state: str, redirect_uri: Optional[str] = None
    ) -> dict:
        """Exchange authorization code for access token."""
        redirect = redirect_uri or settings.MICROSOFT_REDIRECT_URI

        result = self.msal_app.acquire_token_by_authorization_code(
            code=code,
            scopes=MICROSOFT_SCOPES,
            redirect_uri=redirect,
        )

        await self.redis_client.delete(f"microsoft_oauth_state:{state}")

        if "error" in result:
            error_msg = result.get("error_description", result.get("error"))
            logger.error(f"Token exchange failed: {error_msg}")
            raise ValueError(f"Failed to exchange code: {error_msg}")

        logger.info("Successfully exchanged authorization code for tokens")
        return result

    async def get_user_info(self, access_token: str) -> MicrosoftUserInfo:
        """Fetch user information from Microsoft Graph API."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(
                        "Failed to fetch user info. Status: %s, Body: %s",
                        response.status_code,
                        response.text,
                    )
                    raise ValueError("Failed to fetch user information from Microsoft")

                user_data = response.json()

                return MicrosoftUserInfo(
                    id=user_data.get("id"),
                    email=user_data.get("mail") or user_data.get("userPrincipalName"),
                    display_name=user_data.get("displayName"),
                    given_name=user_data.get("givenName"),
                    surname=user_data.get("surname"),
                    user_principal_name=user_data.get("userPrincipalName"),
                )

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching user info: %s", str(e), exc_info=True)
            raise ValueError("Failed to communicate with Microsoft Graph API")

    async def get_or_create_user(self, microsoft_user_info: MicrosoftUserInfo) -> Tuple[User, bool]:
        """
        Get existing user or create new one from Microsoft user info.
        Only creates the User - no organization or other models.

        Returns:
            Tuple of (User, is_new_user)
        """
        existing_user = await self.db.scalar(
            select(User).where(User.email == microsoft_user_info.email)
        )

        if existing_user:
            if existing_user.auth_provider == "local":
                existing_user.auth_provider = "microsoft"
                existing_user.is_verified = True
                await self.db.commit()
                await self.db.refresh(existing_user)

            logger.info(f"Existing user logged in via Microsoft: {microsoft_user_info.email}")
            return existing_user, False

        logger.info(f"Creating new user from Microsoft OAuth: {microsoft_user_info.email}")

        random_password = hash_password(base64.urlsafe_b64encode(os.urandom(32)).decode())

        user_name = microsoft_user_info.display_name or microsoft_user_info.email

        new_user = User(
            email=microsoft_user_info.email,
            name=user_name,
            hashed_password=random_password,
            auth_provider="microsoft",
            is_active=True,
            is_verified=True,
        )

        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)

        logger.info(
            "Created new user via Microsoft OAuth: user_id=%s, email=%s",
            new_user.id,
            new_user.email,
        )

        return new_user, True

    async def complete_oauth_flow(
        self, code: str, state: str, redirect_uri: Optional[str] = None
    ) -> dict:
        """
        Complete the OAuth flow: validate state, exchange code, get user info, create/update user.

        Args:
            code: Authorization code from Microsoft
            state: State parameter for validation
            redirect_uri: Optional redirect URI

        Returns:
            Dictionary with access token, refresh token, and user info

        Raises:
            ValueError: If any step fails
        """
        if not await self.validate_state(state):
            raise ValueError("Invalid or expired state parameter")

        token_response = await self.exchange_code_for_token(code, state, redirect_uri)
        ms_access_token = token_response.get("access_token")

        if not ms_access_token:
            raise ValueError("No access token in response")

        user_info = await self.get_user_info(ms_access_token)

        user, is_new_user = await self.get_or_create_user(user_info)

        access_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
        )

        refresh_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=30),
        )

        logger.info(f"Successful Microsoft OAuth login: {user.email}, is_new_user: {is_new_user}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600 * 24,
            "user_id": str(user.id),
            "email": user.email,
            "is_new_user": is_new_user,
        }
