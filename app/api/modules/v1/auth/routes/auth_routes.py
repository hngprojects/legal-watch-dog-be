# app/api/modules/v1/auth/routes/login_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.api.modules.v1.auth.models.login_models import User, Role, Organization

from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas import LoginRequest, LoginResponse
from app.api.modules.v1.auth.service.auth_service import AuthService

# Initialize logging
setup_logging()
router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app")


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User Login",
    description="Authenticate user and return access/refresh tokens",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    logger.info(f"Login attempt for email: {request.email}")

    # Authenticate user
   # Authenticate user
    user = await AuthService.authenticate_user(db, request.email, request.password)

    if not user:
        logger.warning(f"Failed login attempt for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client_ip = http_request.client.host if http_request else None

    # Generate tokens
    access_token, refresh_token, _ = await AuthService.create_tokens(
        db, user, client_ip
    )

    # Fetch role from DB
    role_result = await db.execute(
        select(Role).where(Role.role_id == user.role_id)
    )
    role = role_result.scalar_one_or_none()

    # Fetch organization from DB
    org_result = await db.execute(
        select(Organization).where(Organization.org_id == user.org_id)
    )
    organization = org_result.scalar_one_or_none()

    # Response data
    response_data = {
        "user": {
            "user_id": str(user.user_id),
            "email": user.email,
            "status": user.status,
        },
        "role": {
            "role_id": str(user.role_id),
            "name": role.name if role else None,
        },
        "organization": {
            "org_id": str(user.org_id),
            "name": organization.name if organization else None,
            "industry": organization.industry if organization else None,
        },
    }


    logger.info(f"Successful login for {user.email} (IP: {client_ip})")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        token_type="Bearer",
        data=response_data,
    )
