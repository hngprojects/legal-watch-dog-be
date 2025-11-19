import logging
from typing import Optional, List
from datetime import timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.modules.v1.onboarding.utils.token_generator import make_token, hash_token
from app.api.core.dependencies.send_mail import send_email
from app.api.core.config import settings
from app.api.modules.v1.onboarding.models.team_invitation import TeamInvitation
from app.api.modules.v1.organization.models.organization_model import Organization
import asyncio

logger = logging.getLogger("app")


async def create_and_send_invite(
    db: AsyncSession,
    current_user,
    role: str,
    team_email: str,
    invitee_name: Optional[str] = None,
):
    """Create TeamInvitation record and send invite email.

    - Generates a secure token and stores only its hash in `TeamInvitation.token`.
    - Commits the DB row and then sends email using the existing
      `send_email(template_name, subject, recipient, context)` function.

    Returns the raw token (useful for tests). Do NOT return this token to the
    API caller in production; it should be delivered via email only.
    """
    # derive organization and sender from the currently logged-in user
    org_id = getattr(current_user, "organization_id", None)
    sender_id = getattr(current_user, "id", None)
    org_name = getattr(current_user, "organization", None)
    sender_name = getattr(current_user, "name", None) or getattr(
        current_user, "email", None
    )
    # attempt to resolve organization name if not present on current_user
    if not org_name and org_id:
        try:
            org_stmt = select(Organization).where(Organization.id == org_id)
            org_res = await db.execute(org_stmt)
            org = org_res.scalar_one_or_none()
            if org:
                org_name = org.name
        except Exception:
            logger.exception("Failed to load organization for invite context")

    # generate token and persist hashed token
    token = make_token()
    stored_hash = hash_token(token)

    invite = TeamInvitation(
        org_id=org_id,
        sender_id=sender_id,
        role=role,
        team_email=team_email,
        token=stored_hash,
    )

    try:
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create TeamInvitation record")
        raise

    # build accept url and email context
    accept_url = f"{settings.LEGAL_WATCH_DOG_BASE_URL}/onboarding/accept?invitation_id={invite.id}&token={token}"
    context = {
        "invitee_name": invitee_name or team_email,
        "org_name": org_name or settings.APP_NAME,
        "sender_name": sender_name or "",
        "accept_url": accept_url,
        "expires_at": invite.expires_at.astimezone(timezone.utc).isoformat(),
    }

    # use existing dependency to send email
    try:
        sent = await send_email(
            template_name="invite.html",
            subject=f"Invitation to join {context['org_name']}",
            recipient=team_email,
            context=context,
        )
        if not sent:
            logger.warning("send_email returned False for invite to %s", team_email)
    except Exception:
        logger.exception("Failed to send invite email to %s", team_email)

    return token


async def create_and_send_bulk_invites(
    db: AsyncSession,
    current_user,
    invites: List[dict],
):
    """Create and send multiple TeamInvitation records and emails.

    Args:
        db: AsyncSession for database operations.
        current_user: The user initiating the invites.
        invites: A list of dictionaries, each containing 'role', 'team_email', and optional 'invitee_name'.

    Returns:
        A summary dictionary with counts of successes and failures.
    """
    results = {"success": 0, "failure": 0}

    async def process_invite(invite):
        try:
            token = await create_and_send_invite(
                db=db,
                current_user=current_user,
                role=invite["role"],
                team_email=invite["team_email"],
                invitee_name=invite.get("invitee_name"),
            )
            results["success"] += 1
        except Exception as e:
            logger.error(
                "Failed to process invite for %s: %s", invite["team_email"], str(e)
            )
            results["failure"] += 1

    # Process all invites concurrently
    await asyncio.gather(*(process_invite(invite) for invite in invites))

    return results
