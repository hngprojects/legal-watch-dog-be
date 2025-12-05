import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import router as api_router
from app.api.core.config import settings
from app.api.core.custom_openapi_docs import custom_openapi
from app.api.core.exceptions import (
    RateLimitExceeded,
    general_exception_handler,
    http_exception_handler,
    rate_limit_exception_handler,
    validation_exception_handler,
)
from app.api.core.logger import setup_logging
from app.api.core.middleware.rate_limiter import RateLimitMiddleware
from app.api.db.database import AsyncSessionLocal, Base, engine
from app.api.events.bridge import RealtimeEventBridge
from app.api.events.factory import get_event_subscriber, shutdown_event_bus
from app.api.events.models import EventTopic
from app.api.modules.v1.billing.seed.plan_seed import seed_billing_plans
from app.api.utils.response_payloads import success_response
from app.api.ws.connection_manager import manager as websocket_manager
from app.api.ws.router import router as websocket_router

setup_logging()
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and release them on shutdown.

    Args:
        app (FastAPI): FastAPI application instance supplied by the framework.

    Returns:
        AsyncIterator[None]: Asynchronous context manager controlling startup/shutdown.

    Raises:
        RuntimeError: If realtime websockets are enabled but misconfigured.

    Examples:
        >>> async with lifespan(app):
        ...     yield
    """

    bridge: RealtimeEventBridge | None = None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_billing_plans(session)

    if settings.ENABLE_REALTIME_WEBSOCKETS:
        try:
            subscriber = await asyncio.wait_for(get_event_subscriber(), timeout=10.0)
            bridge = RealtimeEventBridge(
                subscriber=subscriber,
                manager=websocket_manager,
                topics=[EventTopic.NOTIFICATIONS, EventTopic.SCRAPE_JOBS],
            )
            await bridge.start()
            logger.info("Realtime event bridge started successfully")
        except asyncio.TimeoutError:
            logger.error(
                "Timeout initializing realtime event subscriber (Redis may be unreachable)"
            )
            bridge = None
        except Exception as exc:
            logger.error(f"Failed to initialize realtime bridge: {exc}", exc_info=True)
            bridge = None

    try:
        yield
    finally:
        if bridge is not None:
            await bridge.stop()
        if settings.ENABLE_REALTIME_WEBSOCKETS:
            await shutdown_event_bus()
        await engine.dispose()


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description=f"{settings.APP_NAME} API for managing projects and endpoints",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

APP_URL = settings.APP_URL
DEV_URL = settings.DEV_URL

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600,
    same_site="lax",
    https_only=False,  # must be true for same_site=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[APP_URL, DEV_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add rate limiting middleware - 50 requests per minute while excluding waitlist
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=50,
    excluded_paths=["/api/v1/waitlist", "/health", "/", "/docs"],
)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.openapi = lambda: custom_openapi(app)
app.include_router(api_router)

if settings.ENABLE_REALTIME_WEBSOCKETS:
    app.include_router(websocket_router)


@app.get("/")
def read_root():
    return success_response(
        status_code=200,
        message=f"{settings.APP_NAME} API is running...",
        data={
            "version": settings.APP_VERSION,
            "environment": "Production" if not settings.DEBUG else "Development",
        },
    )


@app.get("/health")
def health_check():
    return success_response(status_code=200, message="API is healthy")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.APP_PORT, reload=False)
