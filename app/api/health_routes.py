from fastapi import APIRouter, Response, status
from opentelemetry.trace import Span, Status, StatusCode
from psycopg import Error as PsycopgError

from app.db.connection import check_database_connection
from app.observability.logging import get_logger
from app.observability.metrics import record_dependency_health
from app.observability.tracing import record_exception_safely, start_span
from app.schemas.health_schema import HealthResponse
from app.services.health_service import get_database_health_status, get_health_status

DATABASE_DEPENDENCY = "database"
DATABASE_HEALTH_SPAN_NAME = "database.health_check"

DATABASE_FAILURE_CONNECTION_ERROR = "connection_error"
DATABASE_FAILURE_HEALTH_CHECK_FAILED = "health_check_failed"

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


def record_database_health_failure(
    *,
    span: Span,
    failure_category: str,
    error: PsycopgError | None = None,
) -> None:
    """
    Record one unhealthy database dependency outcome.

    Failure categories must remain bounded because they are used for
    operational aggregation. Database connection details, SQL statements,
    and exception messages must not be recorded.
    """
    record_dependency_health(DATABASE_DEPENDENCY, False)

    span.set_attribute("app.outcome", "unhealthy")
    span.set_attribute("app.failure.category", failure_category)
    span.set_status(
        Status(
            status_code=StatusCode.ERROR,
            description=failure_category,
        )
    )

    log_fields = {
        "outcome": "unhealthy",
        "failure_category": failure_category,
    }

    if error is not None:
        record_exception_safely(span, error)
        log_fields["exception_type"] = error.__class__.__name__

    logger.warning(
        DATABASE_HEALTH_SPAN_NAME,
        **log_fields,
    )


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
        DATABASE_HEALTH_SPAN_NAME,
        attributes={
            "app.dependency.name": DATABASE_DEPENDENCY,
        },
    ) as span:
        try:
            is_connected = check_database_connection()
        except PsycopgError as error:
            record_database_health_failure(
                span=span,
                failure_category=DATABASE_FAILURE_CONNECTION_ERROR,
                error=error,
            )

            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return get_database_health_status(
                is_connected=False,
                message="Database is not reachable",
                error=error.__class__.__name__,
            )

        if not is_connected:
            record_database_health_failure(
                span=span,
                failure_category=DATABASE_FAILURE_HEALTH_CHECK_FAILED,
            )

            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return get_database_health_status(
                is_connected=False,
                message="Database health check failed",
            )

        record_dependency_health(DATABASE_DEPENDENCY, True)
        span.set_attribute("app.outcome", "healthy")

        return get_database_health_status(is_connected=True)
