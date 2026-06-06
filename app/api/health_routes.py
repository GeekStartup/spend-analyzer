from fastapi import APIRouter, Response, status
from psycopg import Error as PsycopgError

from app.db.connection import check_database_connection
from app.observability.logging import get_logger
from app.observability.metrics import record_dependency_health
from app.observability.tracing import start_span
from app.schemas.health_schema import HealthResponse
from app.services.health_service import get_database_health_status, get_health_status

DATABASE_DEPENDENCY_NAME = "database"

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


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
    with start_span(
        "database.health_check",
        attributes={"db.system": "postgresql"},
    ) as span:
        try:
            is_connected = check_database_connection()
        except PsycopgError as error:
            record_dependency_health(DATABASE_DEPENDENCY_NAME, False)

            span.set_attribute("app.outcome", "failed")
            span.set_attribute("app.failure.category", "connection_error")

            logger.warning(
                "dependency.health",
                dependency=DATABASE_DEPENDENCY_NAME,
                outcome="unhealthy",
                failure_category="connection_error",
                exception_type=error.__class__.__name__,
            )

            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return get_database_health_status(
                is_connected=False,
                message="Database is not reachable",
                error=error.__class__.__name__,
            )

        if not is_connected:
            record_dependency_health(DATABASE_DEPENDENCY_NAME, False)

            span.set_attribute("app.outcome", "failed")
            span.set_attribute("app.failure.category", "health_check_failed")

            logger.warning(
                "dependency.health",
                dependency=DATABASE_DEPENDENCY_NAME,
                outcome="unhealthy",
                failure_category="health_check_failed",
            )

            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return get_database_health_status(
                is_connected=False,
                message="Database health check failed",
            )

        record_dependency_health(DATABASE_DEPENDENCY_NAME, True)
        span.set_attribute("app.outcome", "healthy")

        return get_database_health_status(is_connected=True)
