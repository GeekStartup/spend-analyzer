from fastapi import APIRouter
from psycopg import Error as PsycopgError

from app.db.connection import check_database_connection
from app.errors import DatabaseUnavailableError
from app.observability.metrics import record_dependency_health
from app.schemas.health_schema import HealthResponse
from app.services.health_service import get_database_health_status, get_health_status

DATABASE_DEPENDENCY = "database"

DATABASE_FAILURE_CONNECTION_ERROR = "connection_error"
DATABASE_FAILURE_HEALTH_CHECK_FAILED = "health_check_failed"

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
def database_health_check() -> HealthResponse:
    try:
        is_connected = check_database_connection()
    except PsycopgError as error:
        record_dependency_health(DATABASE_DEPENDENCY, False)
        raise DatabaseUnavailableError(
            "The database health check could not be completed.",
            context={
                "dependency": DATABASE_DEPENDENCY,
                "operation": "health_check",
                "failure_category": DATABASE_FAILURE_CONNECTION_ERROR,
                "cause_type": error.__class__.__name__,
            },
        ) from error

    if not is_connected:
        record_dependency_health(DATABASE_DEPENDENCY, False)
        raise DatabaseUnavailableError(
            "The database health check returned an unhealthy result.",
            context={
                "dependency": DATABASE_DEPENDENCY,
                "operation": "health_check",
                "failure_category": DATABASE_FAILURE_HEALTH_CHECK_FAILED,
            },
        )

    record_dependency_health(DATABASE_DEPENDENCY, True)
    return get_database_health_status(is_connected=True)
