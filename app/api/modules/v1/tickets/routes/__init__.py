from fastapi import APIRouter

# from app.api.modules.v1.tickets.routes import ticket_routes
from app.api.modules.v1.tickets.routes.ticket_external_access_routes import (
    public_router,
)
from app.api.modules.v1.tickets.routes.ticket_external_access_routes import (
    router as external_access_router,
)

router = APIRouter()
# router.include_router(ticket_routes.router)
router.include_router(external_access_router)

__all__ = ["router", "public_router"]
