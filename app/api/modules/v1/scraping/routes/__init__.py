"""Route exports for scraping module."""

from fastapi import APIRouter

from app.api.modules.v1.scraping.routes.scrape_routes import router as scrape_router
from app.api.modules.v1.scraping.routes.source_discovery_route import (
    router as source_discovery_router,
)
from app.api.modules.v1.scraping.routes.source_routes import router as source_router

router = APIRouter()
router.include_router(source_router)
router.include_router(source_discovery_router)
router.include_router(scrape_router)

__all__ = ["router"]
