from time import perf_counter

from fastapi import APIRouter
from opentelemetry.trace import Span, Status, StatusCode
from psycopg import Error as PsycopgError

from app.db.connection import check_database_connection
from app.observability.logging import get_logger
from app.observability.metrics import record_dependency_health
from app.observability.tracing import record_exception_safely, start_span
from app.problem_details import PROBLEM_TYPE_PREFIX, ProblemException
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
    duration_ms: float,
    error: PsycopgError | None = None,
) -> None:
    """Record one safe unhealthy database dependency outcome."""
    record_dependency_health(DATABASE_DEPENDENCY, False)

    span.set_attribute("app.outcome", "unhealthy")
    span.set_attribute("app.failure.category", failure_category)
    span.set_status(
        Status(
            status_code=StatusCode.ERROR,
            description=failure_category,
        )
    )

    if error is not None:
        record_exception_safely(span, error)
        logger.warning(
            "Database health check failed",
            dependency=DATABASE_DEPENDENCY,
            operation="health_check",
            duration_ms=duration_ms,
            exception_type=error.__class__.__name__,
        )
        return

    logger.warning(
        "Database health check returned an unhealthy result",
        dependency=DATABASE_DEPENDENCY,
        operation="health_check",
        duration_ms=duration_ms,
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
def database_health_check() -> HealthResponse:
    started_at = perf_counter()

    with start_span(
        DATABASE_HEALTH_SPAN_NAME,
        attributes={
            "app.dependency.name": DATABASE_DEPENDENCY,
        },
    ) as span:
        try:
            is_connected = check_database_connection()
        except PsycopgError as error:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            record_database_health_failure(
                span=span,
                failure_category=DATABASE_FAILURE_CONNECTION_ERROR,
                duration_ms=duration_ms,
                error=error,
            )

            raise ProblemException(
                status_code=503,
                type=f"{PROBLEM_TYPE_PREFIX}database-unavailable",
                title="Database unavailable",
                detail="The database health check could not be completed.",
            ) from error

        if not is_connected:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            record_database_health_failure(
                span=span,
                failure_category=DATABASE_FAILURE_HEALTH_CHECK_FAILED,
                duration_ms=duration_ms,
            )

            raise ProblemException(
                status_code=503,
                type=f"{PROBLEM_TYPE_PREFIX}database-unavailable",
                title="Database unavailable",
                detail="The database health check returned an unhealthy result.",
            )

        record_dependency_health(DATABASE_DEPENDENCY, True)
        span.set_attribute("app.outcome", "healthy")

        return get_database_health_status(is_connected=True)
