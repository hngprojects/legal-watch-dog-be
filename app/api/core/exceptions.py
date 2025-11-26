import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.utils.response_payloads import error_response

logger = logging.getLogger("app")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic request validation errors and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (RequestValidationError): The validation error raised by FastAPI/Pydantic.

    Returns:
        JSONResponse: Standardized error response containing field-level validation messages.
    """
    errors = {}
    for err in exc.errors():
        loc = err["loc"][-1]
        msg = err["msg"]
        if msg.startswith("Value error,"):
            msg = msg.replace("Value error,", "").strip()
        errors[loc] = [msg]

    return error_response(
        status_code=422,
        message="Validation failed",
        error="VALIDATION_ERROR",
        errors=errors,
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTP exceptions (4xx/5xx) and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (HTTPException): The HTTP exception raised by FastAPI.

    Returns:
        JSONResponse: Standardized error response with HTTP status code and message.
    """
    logger.error(f"HTTP exception: {exc.detail} ({exc.status_code})")

    return error_response(
        status_code=exc.status_code,
        error="HTTP_ERROR",
        message=exc.detail,
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (Exception): The unhandled exception.

    Returns:
        JSONResponse: Standardized 500 error response.
    """
    logger.exception(f"Unhandled exception: {exc}")

    return error_response(
        status_code=500,
        error="INTERNAL_SERVER_ERROR",
        message="Internal server error",
    )


class PasswordReuseError(Exception):
    """
    Custom exception to indicate that a user is trying to reuse a previously used password.
    """

    pass
