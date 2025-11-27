import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.api.core.dependencies.redis_service import check_rate_limit
from app.api.modules.v1.contact_us.routes.docs.contact_route import (
    contact_us_custom_errors,
    contact_us_custom_success,
    contact_us_responses,
)
from app.api.modules.v1.contact_us.schemas.contact_us import (
    ContactUsRequest,
    ContactUsResponse,
)
from app.api.modules.v1.contact_us.service.contact_us import ContactUsService
from app.api.utils.response_payloads import (
    error_response,
    success_response,
)

router = APIRouter(prefix="/contact-us", tags=["Contact Us"])

logger = logging.getLogger("app")

MAX_CONTACT_ATTEMPTS = 3
RATE_LIMIT_WINDOW_SECONDS = 3600


@router.post(
    "",
    response_model=ContactUsResponse,
    status_code=status.HTTP_200_OK,
    responses=contact_us_responses,
)
async def contact_us(
    payload: ContactUsRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Submit a contact form.

    Processes contact form submissions and sends notification emails
    to both the admin team and the user who submitted the form.

    Rate Limited: 3 submissions per hour per email address and IP address.

    Args:
        payload (ContactUsRequest): Contact form data including full name,
            phone number, email, and message.
        background_tasks (BackgroundTasks): FastAPI background tasks instance
            for async email operations.
        request (Request): FastAPI request object for rate limiting.

    Returns:
        dict: Standardized success or error response with status, message,
            and data/error details.

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    try:
        ip_address: Optional[str] = request.client.host if request.client else None

        email_allowed = await check_rate_limit(
            f"contact:email:{payload.email}",
            max_attempts=MAX_CONTACT_ATTEMPTS,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )

        if not email_allowed:
            logger.warning(f"Rate limit exceeded for email: {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many contact form submissions. Please try again in 1 hour.",
            )

        if ip_address:
            ip_allowed = await check_rate_limit(
                f"contact:ip:{ip_address}",
                max_attempts=MAX_CONTACT_ATTEMPTS * 2,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

            if not ip_allowed:
                logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts from this IP. Try again in 1 hour.",
                )

        service = ContactUsService()
        result = await service.submit_contact_form(payload, background_tasks)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Thank you for contacting us. We'll get back to you soon!",
            data=result,
        )

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning("Contact form validation failed for email=%s: %s", payload.email, str(e))
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))

    except Exception as e:
        logger.error(
            "Failed to process contact form for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Failed to submit your message. Please try again later.",
        )


contact_us._custom_errors = contact_us_custom_errors
contact_us._custom_success = contact_us_custom_success
