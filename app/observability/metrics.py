from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

APP_EXCEPTIONS_TOTAL = Counter(
    "app_exceptions_total",
    "Total number of application exceptions.",
    ["exception_category"],
)

APP_DEPENDENCY_HEALTH_STATUS = Gauge(
    "app_dependency_health_status",
    "Dependency health status. 1 means healthy, 0 means unhealthy.",
    ["dependency"],
)

STATEMENT_INGESTION_ATTEMPTS_TOTAL = Counter(
    "statement_ingestion_attempts_total",
    "Total number of statement ingestion attempts.",
)

STATEMENT_INGESTION_SUCCESS_TOTAL = Counter(
    "statement_ingestion_success_total",
    "Total number of successful statement ingestions.",
    ["content_type"],
)

STATEMENT_INGESTION_FAILURES_TOTAL = Counter(
    "statement_ingestion_failures_total",
    "Total number of failed statement ingestions.",
    ["failure_category"],
)

STATEMENT_UPLOAD_SIZE_BYTES = Histogram(
    "statement_upload_size_bytes",
    "Uploaded statement size in bytes.",
    ["content_type"],
)


def configure_http_metrics(
    app: FastAPI,
    *,
    enabled: bool,
    metrics_path: str,
) -> None:
    if not enabled:
        return

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[metrics_path],
    ).instrument(app).expose(
        app,
        endpoint=metrics_path,
        include_in_schema=False,
    )


def record_app_exception(exception_category: str) -> None:
    APP_EXCEPTIONS_TOTAL.labels(
        exception_category=exception_category,
    ).inc()


def record_dependency_health(dependency: str, is_healthy: bool) -> None:
    APP_DEPENDENCY_HEALTH_STATUS.labels(
        dependency=dependency,
    ).set(1 if is_healthy else 0)


def record_statement_ingestion_attempt() -> None:
    STATEMENT_INGESTION_ATTEMPTS_TOTAL.inc()


def record_statement_ingestion_success(content_type: str, file_size_bytes: int) -> None:
    STATEMENT_INGESTION_SUCCESS_TOTAL.labels(
        content_type=content_type,
    ).inc()

    STATEMENT_UPLOAD_SIZE_BYTES.labels(
        content_type=content_type,
    ).observe(file_size_bytes)


def record_statement_ingestion_failure(failure_category: str) -> None:
    STATEMENT_INGESTION_FAILURES_TOTAL.labels(
        failure_category=failure_category,
    ).inc()
