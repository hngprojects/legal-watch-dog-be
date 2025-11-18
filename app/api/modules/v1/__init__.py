from fastapi import APIRouter
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router
from app.api.modules.v1.auth.routes.login_route import router as auth_router

router = APIRouter(prefix="/v1")
router.include_router(waitlist_router)
router.include_router(auth_router)
