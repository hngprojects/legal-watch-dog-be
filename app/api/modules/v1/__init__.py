from fastapi import APIRouter
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router
from app.api.modules.v1.auth.routes.auth_routes import router as register_router
from app.api.modules.v1.auth.routes.login_route import router as auth_router
from app.api.modules.v1.auth.routes.reset_password import (
    router as password_reset_router,
)
from app.api.modules.v1.tickets.routes.ticket_routes import router as ticket_router
from app.api.modules.v1.tickets.routes.invitation_routes import (
    router as invitation_router,
)

router = APIRouter(prefix="/v1")
router.include_router(waitlist_router)
router.include_router(register_router)
router.include_router(auth_router)
router.include_router(password_reset_router)
router.include_router(ticket_router)
router.include_router(invitation_router)
