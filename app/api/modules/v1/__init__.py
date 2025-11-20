from fastapi import APIRouter

from app.api.modules.v1.auth.routes.auth_routes import router as register_router
from app.api.modules.v1.auth.routes.login_route import router as auth_router
from app.api.modules.v1.auth.routes.reset_password import (
    router as password_reset_router,
)
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router

router = APIRouter(prefix="/v1")
router.include_router(waitlist_router)
router.include_router(register_router)
router.include_router(auth_router)
router.include_router(password_reset_router)
