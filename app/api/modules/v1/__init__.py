from fastapi import APIRouter

from app.api.modules.v1.auth.routes.auth_routes import router as register_router
from app.api.modules.v1.auth.routes.login_route import router as auth_router
from app.api.modules.v1.auth.routes.reset_password import (
    router as password_reset_router,
)
from app.api.modules.v1.billing import billing_router
from app.api.modules.v1.jurisdictions.routes.jurisdiction_route import (
    router as juridiction_router,
)
from app.api.modules.v1.organization.routes.organization_route import (
    router as organization_router,
)
from app.api.modules.v1.projects.routes.project_routes import router as project_router
from app.api.modules.v1.scraping.routes import router as scraping_router
from app.api.modules.v1.search.routes import data_revision_search_router
from app.api.modules.v1.users.routes.users_route import router as users_router
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router

router = APIRouter(prefix="/v1")
router.include_router(waitlist_router)
router.include_router(register_router)
router.include_router(organization_router)
router.include_router(users_router)
router.include_router(auth_router)
router.include_router(password_reset_router)
router.include_router(scraping_router)
router.include_router(project_router)
router.include_router(juridiction_router)
router.include_router(billing_router)
router.include_router(data_revision_search_router)
