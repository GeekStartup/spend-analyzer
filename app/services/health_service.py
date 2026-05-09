from app.config import settings
from app.schemas.health_schema import HealthCheck, HealthResponse, ServiceMetadata


def get_service_metadata() -> ServiceMetadata:
    return ServiceMetadata(
        name=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )


def get_health_status() -> HealthResponse:
    return HealthResponse(
        status="OK",
        service=get_service_metadata(),
        checks={
            "application": HealthCheck(
                status="OK",
                message="Application is running",
            )
        },
    )


def get_database_health_status(
    *,
    is_connected: bool,
    message: str | None = None,
    error: str | None = None,
) -> HealthResponse:
    if is_connected:
        return HealthResponse(
            status="OK",
            service=get_service_metadata(),
            checks={
                "database": HealthCheck(
                    status="OK",
                    message=message or "Database is reachable",
                )
            },
        )

    return HealthResponse(
        status="ERROR",
        service=get_service_metadata(),
        checks={
            "database": HealthCheck(
                status="ERROR",
                message=message or "Database is not reachable",
                error=error,
            )
        },
    )
