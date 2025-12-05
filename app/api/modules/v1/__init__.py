from fastapi import APIRouter

from app.api.modules.v1.auth.routes.apple_auth_route import router as apple_auth_router
from app.api.modules.v1.auth.routes.auth_routes import router as register_router
from app.api.modules.v1.auth.routes.login_route import router as auth_router
from app.api.modules.v1.auth.routes.oauth_google import router as oauth_google_router
from app.api.modules.v1.auth.routes.oauth_microsoft import router as oauth_microsoft_router
from app.api.modules.v1.auth.routes.reset_password import (
    router as password_reset_router,
)
from app.api.modules.v1.billing.routes import billing_router
from app.api.modules.v1.contact_us.routes.contact_us import router as contact_us_router
from app.api.modules.v1.hire_specialists.routes.specialist_routes import router as specialist_router
from app.api.modules.v1.jurisdictions.routes.jurisdiction_route import (
    router as juridiction_router,
)
from app.api.modules.v1.notifications.routes.notification_route import router as notification_router
from app.api.modules.v1.notifications.routes.ticket_notification_routes import (
    router as ticket_notif_router,
)
from app.api.modules.v1.organization.routes import router as organization_router
from app.api.modules.v1.projects.routes.project_routes import router as project_router
from app.api.modules.v1.scraping.routes import router as scraping_router
from app.api.modules.v1.search.routes import data_revision_search_router
from app.api.modules.v1.tickets.routes import (
    guest_access_router,
    participant_router,
)
from app.api.modules.v1.users.routes.users_route import router as users_router
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router

router = APIRouter(prefix="/v1")
router.include_router(waitlist_router)
router.include_router(contact_us_router)
router.include_router(specialist_router)
router.include_router(register_router)
router.include_router(oauth_microsoft_router)
router.include_router(oauth_google_router)
router.include_router(apple_auth_router)
router.include_router(organization_router)
router.include_router(users_router)
router.include_router(auth_router)
router.include_router(password_reset_router)
router.include_router(scraping_router)
router.include_router(project_router)
router.include_router(juridiction_router)
router.include_router(notification_router)
router.include_router(billing_router)
router.include_router(data_revision_search_router)
router.include_router(ticket_notif_router)
router.include_router(participant_router)
router.include_router(guest_access_router)
