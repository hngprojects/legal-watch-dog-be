import os
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.api.core.config import settings
from app.api import router as api_router
from app.api.db.database import engine, Base
from app.api.utils.response_payloads import success_response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description=f"{settings.APP_NAME} API for managing projects and endpoints",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan, 
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "app/api/core/dependencies/email/templates")
email_templates = Jinja2Templates(directory=TEMPLATE_DIR)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)


@app.get("/")
def read_root():
    return success_response(
        status_code=200,
        message=f"{settings.APP_NAME} API is running...",
        data={
            "version": settings.APP_VERSION,
            "environment": "Production" if not settings.DEBUG else "Development"
        }
    )


@app.get("/health")
def health_check():
    return success_response(
        status_code=200,
        message="API is healthy"
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=False
    )
