from fastapi import FastAPI

from app.api.health_routes import router as health_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered personal finance spend analyzer",
        version=settings.app_version,
    )

    app.include_router(health_router)
    
    return app

app = create_app()