from fastapi import APIRouter, Response, status
from psycopg import Error as PsycopgError

from app.db.connection import check_database_connection
from app.schemas.health_schema import HealthResponse
from app.services.health_service import get_database_health_status, get_health_status


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
)
def health_check() -> HealthResponse:
    return get_health_status()


@router.get(
    "/health/db",
    response_model=HealthResponse,
    response_model_exclude_none=True,
)
def database_health_check(response: Response) -> HealthResponse:
    try:
        is_connected = check_database_connection()
    except PsycopgError as error:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return get_database_health_status(
            is_connected=False,
            message="Database is not reachable",
            error=error.__class__.__name__,
        )

    if not is_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return get_database_health_status(
            is_connected=False,
            message="Database health check failed",
        )

    return get_database_health_status(is_connected=True)
