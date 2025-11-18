from datetime import datetime, timezone
from typing import Tuple
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.auth.models.otp_model import OTP
from app.api.modules.v1.auth.schemas.register import RegisterRequest
from app.api.core.dependencies.send_mail import send_email
from app.api.core.dependencies.redis_service import (
    store_otp,
    verify_otp as verify_otp_redis,
)
from app.api.utils.permissions import ADMIN_PERMISSIONS
from app.api.utils.password import hash_password
from app.api.utils.jwt import create_access_token
from app.api.core.logger import setup_logging
import logging

setup_logging()
logger = logging.getLogger("app")

ADMIN_ROLE_NAME = "admin"


async def register_organization(
    db: AsyncSession,
    data: RegisterRequest,
    background_tasks: BackgroundTasks | None = None,
) -> Tuple[User, str]:
    # 1. Create Organization
    logger.info(f"Starting registration for company: {data.name}, email: {data.email}")
    org = Organization(name=data.name, industry=data.industry)
    db.add(org)
    await db.flush()  # get org.id

    # 2. Create Admin Role if not exists
    role = await db.scalar(
        select(Role).where(Role.name == ADMIN_ROLE_NAME, Role.organization_id == org.id)
    )
    if not role:
        logger.info(f"Creating admin role for organization: {org.id}")
        role = Role(
            name=ADMIN_ROLE_NAME,
            description="Organization Administrator",
            organization_id=org.id,
            permissions=ADMIN_PERMISSIONS,
        )
        db.add(role)
        await db.flush()

    # 3. Hash password
    hashed_pw = hash_password(data.password)

    # 4. Create User (admin)
    user = User(
        organization_id=org.id,
        role_id=role.id,
        email=data.email,
        hashed_password=hashed_pw,
        name=data.name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    logger.info(f"Created admin user: {user.email} for organization: {org.id}")

    # 5. Generate OTP and store in Redis
    otp_code = OTP.generate_code()
    await store_otp(str(user.id), otp_code, ttl_minutes=10)

    await db.commit()
    logger.info(f"Generated OTP for user: {user.email} and stored in Redis")

    # 6. Send OTP email using HTML template. Use BackgroundTasks if provided so the
    # request doesn't block on external IO.
    # Build context compatible with send_email(context: dict)
    email_context = {
        "organization_email": data.email,
        "organization_name": data.name,
        "otp": otp_code,
        "year": 2025,
    }
    if background_tasks is not None:
        # pass the context as the only argument to send_email
        background_tasks.add_task(send_email, email_context)
        logger.info(f"Scheduled OTP email to be sent to: {data.email}")
    else:
        await send_email(email_context)
        logger.info(f"Sent OTP email to: {data.email}")
    # create access token for the new user
    access_token = create_access_token(
        user_id=str(user.id), organization_id=str(org.id), role_id=str(role.id)
    )
    return user, access_token


async def verify_otp(db: AsyncSession, email: str, code: str) -> bool:
    """Verify OTP from Redis and mark user as verified in DB."""
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        logger.warning(f"OTP verification failed: user not found for email {email}")
        return False

    # Verify OTP from Redis
    is_valid = await verify_otp_redis(str(user.id), code)

    if not is_valid:
        logger.warning(
            f"OTP verification failed: invalid or expired OTP for user {user.email}"
        )
        return False

    # Save OTP to database for audit trail
    otp = OTP(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc),  # Already expired/used
        is_used=True,
    )
    db.add(otp)

    # Mark user as verified
    user.is_verified = True
    db.add(user)
    await db.commit()

    logger.info(f"OTP verified for user: {user.email}")
    return True
