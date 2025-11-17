from fastapi import APIRouter
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router

router = APIRouter(prefix="/v1")
router.include_router(waitlist_router)