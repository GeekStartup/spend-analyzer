from app.config import settings
from app.schemas.health_schema import HealthResponse


def get_health_status() -> HealthResponse:
    return HealthResponse(
        status="OK",
        service=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )
