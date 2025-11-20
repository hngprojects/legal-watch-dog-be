import logging
import uuid

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.utils.response_payloads import fail_response

logger = logging.getLogger("app")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {err["loc"][-1]: [err["msg"]] for err in exc.errors()}
    trace_id = str(uuid.uuid4())
    logger.error(f"Validation error: {exc.errors()}, trace_id: {trace_id}")
    return fail_response(
        status_code=400,
        message="Validation failed",
        data={"errors": errors, "trace_id": trace_id},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = str(uuid.uuid4())
    logger.error(f"HTTP exception: {exc.detail}, status: {exc.status_code}, trace_id: {trace_id}")
    return fail_response(
        status_code=exc.status_code,
        message=exc.detail,
        data={"trace_id": trace_id},
    )


async def general_exception_handler(request: Request, exc: Exception):
    trace_id = str(uuid.uuid4())
    logger.exception(f"Unhandled exception: {exc}, trace_id: {trace_id}")
    return fail_response(
        status_code=500,
        message="Internal server error",
        data={"trace_id": trace_id},
    )


class PasswordReuseError(Exception):
    pass
