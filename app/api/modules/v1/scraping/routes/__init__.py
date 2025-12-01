"""Route exports for scraping module."""

from fastapi import APIRouter

from app.api.modules.v1.scraping.routes.manual_scrape_routes import (
    router as manual_scrape_router,
)
from app.api.modules.v1.scraping.routes.source_discovery_route import (
    router as source_discovery_router,
)
from app.api.modules.v1.scraping.routes.source_routes import router as source_router

router = APIRouter()
router.include_router(source_router)
router.include_router(source_discovery_router)
router.include_router(manual_scrape_router)

__all__ = ["router"]
