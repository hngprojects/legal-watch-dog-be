import logging
from datetime import datetime, timezone
from typing import Tuple

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.redis_service import (
    store_otp,
)
from app.api.core.dependencies.redis_service import (
    verify_otp as verify_otp_redis,
)
from app.api.core.dependencies.send_mail import send_email
from app.api.core.logger import setup_logging
from app.api.modules.v1.auth.models.otp_model import OTP
from app.api.modules.v1.auth.schemas.register import RegisterRequest
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import create_access_token
from app.api.utils.password import hash_password
from app.api.utils.permissions import ADMIN_PERMISSIONS

setup_logging()
logger = logging.getLogger("app")

ADMIN_ROLE_NAME = "admin"


async def register_organization(
    db: AsyncSession,
    data: RegisterRequest,
    background_tasks: BackgroundTasks | None = None,
) -> Tuple[User, str]:
    logger.info(f"Starting registration for company: {data.name}, email: {data.email}")
    org = Organization(name=data.name, industry=data.industry)
    db.add(org)
    await db.flush()

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

    hashed_pw = hash_password(data.password)

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email=data.email,
        hashed_password=hashed_pw,
        name=data.name,
        auth_provider="local",
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    logger.info(f"Created admin user: {user.email} for organization: {org.id}")

    otp_code = OTP.generate_code()
    await store_otp(str(user.id), otp_code, ttl_minutes=10)

    await db.commit()
    logger.info(f"Generated OTP for user: {user.email} and stored in Redis {otp_code}")

    context = {
        "organization_email": data.email,
        "organization_name": data.name,
        "otp": otp_code,
        "year": 2025,
    }
    subject = "Your OTP Code for Legal Watch Dog Registration"
    recepient = data.email
    template_name = "otp.html"

    if background_tasks is not None:
        background_tasks.add_task(send_email, template_name, subject, recepient, context)
        logger.info(f"Scheduled OTP email to be sent to: {data.email}")
    else:
        await send_email(template_name, subject, recepient, context)
        logger.info(f"Sent OTP email to: {data.email}")

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
        logger.warning(f"OTP verification failed: invalid or expired OTP for user {user.email}")
        return False

    # Save OTP to database for audit trail
    otp = OTP(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None),  # Already expired/used
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),  # Already expired/used
        is_used=True,
    )
    db.add(otp)

    # Mark user as verified
    user.is_verified = True
    db.add(user)
    await db.commit()

    logger.info(f"OTP verified for user: {user.email}")
    return True


async def get_organisation_by_email(db: AsyncSession, user_email: str) -> User | None:
    """Fetch organization by email."""

    return await db.scalar(select(User).where(User.email == user_email))
