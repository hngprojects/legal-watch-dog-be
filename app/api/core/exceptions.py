import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.utils.response_payloads import fail_response

logger = logging.getLogger("app")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {err["loc"][-1]: [err["msg"]] for err in exc.errors()}
    logger.error(f"Validation error: {exc.errors()}")
    return fail_response(
        status_code=422,
        message="Validation failed",
        error=errors,
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP exception: {exc.detail}, status: {exc.status_code}")
    return fail_response(
        status_code=exc.status_code,
        message=exc.detail,
    )


async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return fail_response(
        status_code=500,
        message="Internal server error",
    )


class PasswordReuseError(Exception):
    pass
