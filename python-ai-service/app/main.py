from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Internal AI service for PublishPro-AI. "
        "It is meant to be called by the Spring Boot backend, not by browsers."
    ),
)

# Every route lives under /api/v1 so a future /api/v2 can sit beside it.
app.include_router(health.router, prefix="/api/v1")
