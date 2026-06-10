from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

UPLOAD_SIZE_BUCKETS_BYTES = (
    10 * 1024,
    50 * 1024,
    100 * 1024,
    250 * 1024,
    500 * 1024,
    1 * 1024 * 1024,
    2 * 1024 * 1024,
    5 * 1024 * 1024,
    10 * 1024 * 1024,
)

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

AUTH_FAILURES_TOTAL = Counter(
    "auth_failures_total",
    "Total number of authentication failures.",
    ["failure_category"],
)

FILE_STORAGE_FAILURES_TOTAL = Counter(
    "file_storage_failures_total",
    "Total number of file-storage failures.",
    ["failure_category"],
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
    buckets=UPLOAD_SIZE_BUCKETS_BYTES,
)


def ensure_metrics_path_available(app: FastAPI, metrics_path: str) -> None:
    conflicting_routes = [
        route for route in app.routes if getattr(route, "path", None) == metrics_path
    ]

    if conflicting_routes:
        raise ValueError(
            f"Metrics path {metrics_path!r} conflicts with an existing "
            "application route"
        )


def configure_http_metrics(
    app: FastAPI,
    *,
    enabled: bool,
    metrics_path: str,
) -> None:
    if not enabled:
        return

    ensure_metrics_path_available(app, metrics_path)

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


def record_auth_failure(failure_category: str) -> None:
    AUTH_FAILURES_TOTAL.labels(
        failure_category=failure_category,
    ).inc()


def record_file_storage_failure(failure_category: str) -> None:
    FILE_STORAGE_FAILURES_TOTAL.labels(
        failure_category=failure_category,
    ).inc()


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
