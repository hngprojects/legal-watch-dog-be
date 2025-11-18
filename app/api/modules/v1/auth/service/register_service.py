from datetime import datetime, timezone
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.auth.models.otp_model import OTP
from app.api.modules.v1.auth.schemas.register import RegisterRequest
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.auth.service.template_utils import render_template
import logging
import bcrypt

ADMIN_ROLE_NAME = "admin"

logger = logging.getLogger("app")

async def register_organization_user(
    db: AsyncSession, data: RegisterRequest
) -> User:
    # 1. Create Organization
    logger.info(f"Starting registration for company: {data.company_name}, email: {data.email}")
    org = Organization(name=data.company_name)
    db.add(org)
    await db.flush()  # get org.id

    # 2. Create Admin Role if not exists
    role = await db.scalar(select(Role).where(Role.name == ADMIN_ROLE_NAME, Role.organization_id == org.id))
    if not role:
        logger.info(f"Creating admin role for organization: {org.id}")
        role = Role(name=ADMIN_ROLE_NAME, description="Organization Admin", organization_id=org.id, permissions={"can_create_roles": True, "can_invite_users": True})
        db.add(role)
        await db.flush()

    # 3. Hash password
    hashed_pw = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()

    # 4. Create User (admin)
    user = User(
        organization_id=org.id,
        role_id=role.id,
        email=data.email,
        hashed_password=hashed_pw,
        name=data.company_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    logger.info(f"Created admin user: {user.email} for organization: {org.id}")

    # 5. Generate OTP
    otp_code = OTP.generate_code()
    otp = OTP(
        user_id=user.id,
        code=otp_code,
        expires_at=OTP.expiry_time(),
        is_used=False,
    )
    db.add(otp)
    await db.commit()
    logger.info(f"Generated OTP for user: {user.email}")

    # 6. Send OTP email using HTML template
    html_content = render_template(
        "base.html",
        {
            "subject": "Your OTP Code",
            "user_name": data.company_name,
            "otp": otp_code,
            "year": 2025
        }
    )
    context = {
        "organization_name": data.company_name,
        "organization_email": data.email,
        "text_content": html_content
    }
    await send_email(context)
    logger.info(f"Sent OTP email to: {data.email}")
    return user

async def verify_otp(db: AsyncSession, email: str, code: str) -> bool:
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        logger.warning(f"OTP verification failed: user not found for email {email}")
        return False
    otp = await db.scalar(
        select(OTP).where(
            OTP.user_id == user.id,
            OTP.code == code,
            OTP.is_used == False,
            OTP.expires_at > datetime.now(timezone.utc),
        )
    )
    if not otp:
        logger.warning(f"OTP verification failed: invalid or expired OTP for user {user.email}")
        return False
    otp.is_used = True
    user.is_verified = True
    db.add(otp)
    db.add(user)
    await db.commit()
    logger.info(f"OTP verified for user: {user.email}")
    return True
