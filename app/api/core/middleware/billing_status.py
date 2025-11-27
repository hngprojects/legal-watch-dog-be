import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.db.database import get_db
from app.api.modules.v1.organization.models.organization_model import Organization

logger = logging.getLogger("app")

class BillingStatusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract organization_id from request (customize as needed)
        organization_id = request.headers.get("X-Organization-ID")
        if not organization_id:
            return JSONResponse(status_code=400, content={"detail": "Organization ID missing"})

        db: AsyncSession = await get_db().__anext__()
        organization = await db.get(Organization, organization_id)
        if not organization:
            return JSONResponse(status_code=404, content={"detail": "Organization not found"})

        billing_info = organization.billing_info or {}
        if not billing_info.get("is_active", True):
            return JSONResponse(status_code=403, content={"detail": "Billing expired. Access denied."})

        return await call_next(request)
