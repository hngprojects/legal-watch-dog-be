from fastapi import APIRouter

from app.api.modules.v1.billing import webhooks
from app.api.modules.v1.billing.routes import admin, billing, invoices

billing_router = APIRouter()


billing_router.include_router(billing.router)
billing_router.include_router(invoices.router)
billing_router.include_router(admin.router)
billing_router.include_router(webhooks.router)


__all__ = ["billing_router"]
