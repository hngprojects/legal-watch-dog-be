import logging
from typing import Optional, List
from datetime import timezone, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.modules.v1.onboarding.utils.token_generator import (
    make_token,
    hash_token,
)
from app.api.core.dependencies.send_mail import send_email
from app.api.core.config import settings
from app.api.modules.v1.onboarding.models.team_invitation import (
    TeamInvitation,
    InvitationStatus,
)
from app.api.modules.v1.organization.models.organization_model import (
    Organization,
)
import asyncio

logger = logging.getLogger("app")


# --------------------------------------------------------------------
# 🔹 Single Invite
# --------------------------------------------------------------------
async def create_and_send_invite(
    db: AsyncSession,
    current_user,
    role: str,
    team_email: str,
    invitee_name: Optional[str] = None,
):
    """Create TeamInvitation record and send invite email.

    - Prevents duplicate pending unexpired invites.
    - Generates a secure token (stores only hash).
    - Sends structured HTML email.
    """

    org_id = getattr(current_user, "organization_id", None)
    sender_id = getattr(current_user, "id", None)

    # Check for existing pending invite
    stmt = select(TeamInvitation).where(
        TeamInvitation.org_id == org_id,
        TeamInvitation.team_email == team_email,
        TeamInvitation.status == InvitationStatus.PENDING,
        TeamInvitation.expires_at > datetime.now(timezone.utc),
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        logger.info(
            "Duplicate invite blocked for %s in org %s", team_email, org_id
        )
        return {
            "email": team_email,
            "status": "duplicate",
            "message": "An active invitation already exists.",
        }

    org_name = getattr(current_user, "organization", None)
    sender_name = (
        getattr(current_user, "name", None)
        or getattr(current_user, "email", None)
    )

    if not org_name and org_id:
        try:
            stmt = select(Organization).where(Organization.id == org_id)
            result = await db.execute(stmt)
            org = result.scalar_one_or_none()
            if org:
                org_name = org.name
        except Exception:
            logger.exception("Failed to load organization name")

    raw_token = make_token()
    token_hash = hash_token(raw_token)

    invite = TeamInvitation(
        org_id=org_id,
        sender_id=sender_id,
        role=role,
        team_email=team_email,
        token=token_hash,
    )

    try:
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
    except Exception:
        await db.rollback()
        logger.exception("Failed to create TeamInvitation")
        raise

    accept_url = (
        f"{settings.LEGAL_WATCH_DOG_BASE_URL}/onboarding/accept"
        f"?invitation_id={invite.id}&token={raw_token}"
    )

    context = {
        "invitee_name": invitee_name or team_email,
        "org_name": org_name or settings.APP_NAME,
        "sender_name": sender_name,
        "accept_url": accept_url,
        "expires_at": invite.expires_at.astimezone(timezone.utc).isoformat(),
    }

    try:
        sent = await send_email(
            template_name="invite.html",
            subject=f"Invitation to join {context['org_name']}",
            recipient=team_email,
            context=context,
        )
        if not sent:
            logger.warning("send_email returned False for %s", team_email)
    except Exception:
        logger.exception("Failed to send email to %s", team_email)

    return {
        "email": team_email,
        "status": "sent",
        "invitation_id": invite.id,
    }


# --------------------------------------------------------------------
# 🔹 Bulk Invite
# --------------------------------------------------------------------
async def create_and_send_bulk_invites(
    db: AsyncSession,
    current_user,
    invites: List[dict],
):
    """
    Process multiple invitations in bulk.

    Returns:
        {
            "summary": { "success": X, "failure": Y, "duplicate": Z },
            "results": [ ...individual invite results... ]
        }
    """

    summary = {"success": 0, "failure": 0, "duplicate": 0}
    results = []

    async def process(invite):
        try:
            res = await create_and_send_invite(
                db=db,
                current_user=current_user,
                role=invite["role"],
                team_email=invite["team_email"],
                invitee_name=invite.get("invitee_name"),
            )

            results.append(res)

            # count summary
            if res["status"] == "sent":
                summary["success"] += 1
            elif res["status"] == "duplicate":
                summary["duplicate"] += 1
            else:
                summary["failure"] += 1

        except Exception as e:
            logger.error(
                "Failed bulk-process invite for %s: %s",
                invite["team_email"],
                str(e),
            )
            summary["failure"] += 1
            results.append(
                {
                    "email": invite["team_email"],
                    "status": "error",
                    "message": str(e),
                }
            )

    await asyncio.gather(*(process(inv) for inv in invites))

    return {"summary": summary, "results": results}
