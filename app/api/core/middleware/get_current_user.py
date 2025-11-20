import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.redis_service import is_token_denylisted
from app.api.db.database import get_db
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import decode_token

logger = logging.getLogger("app")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate JWT access token, check denylist, and return the current user.
    Raises 401 if token is invalid, expired, or revoked.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:

        payload = decode_token(token)
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")

        if not user_id or not jti:
            raise credentials_exception

        if await is_token_denylisted(jti):
            logger.warning(f"Token jti={jti} is denylisted")
            raise credentials_exception

    except Exception as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise credentials_exception

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise credentials_exception

    return user
