from fastapi import FastAPI

from app.api.routes import content, health, publishing, thumbnails

app = FastAPI(title="PublishPro-AI Service", version="0.2.0")
app.include_router(health.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(publishing.router, prefix="/api/v1")
app.include_router(thumbnails.router, prefix="/api/v1")
