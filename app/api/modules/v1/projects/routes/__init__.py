from fastapi import APIRouter

from .audit_routes import router as audit_router
from .project_routes import router as project_router

# from .jurisdiction_routes import router as jurisdiction_router

router = APIRouter()

# existing project routes
router.include_router(project_router)

# your audit logging routes (PROJ-006)
router.include_router(audit_router)
