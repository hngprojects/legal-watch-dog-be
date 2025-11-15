import os
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from app.api.core.config import settings
from app.api import router as api_router


app = FastAPI(
    title="Legal Watch Dog API",
    description="Legal Watch Dog API for managing projects and endpoints",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
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
    return {
        "message": f"{settings.APP_NAME} API is running...",
        "version": settings.APP_VERSION,
        "environment": "Production" if not settings.DEBUG else "Development"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=False
    )
