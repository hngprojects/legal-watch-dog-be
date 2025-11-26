import logging
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.users.models import User

setup_logging()
logger = logging.getLogger(__name__) 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extracts user from JWT token and fetches from DB.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = UUID(user_id) 
    except (jwt.PyJWTError, ValueError) as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Fetch user from DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user

async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require admin role.
    
    Raises:
        HTTPException: If user is not admin or owner
    """
    if current_user.role not in ["admin", "owner"]:
        logger.warning("Admin access denied", extra={
            "user_id": str(current_user.id),
            "user_role": current_user.role
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user
