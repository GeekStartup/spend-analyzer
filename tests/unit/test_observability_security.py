import ast
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability import logging as observability_logging
from app.observability import metrics
from app.observability.middleware import RequestContextMiddleware
from app.problem_details import register_problem_handlers

APPLICATION_PACKAGE_PATHS = (
    Path("app/api"),
    Path("app/auth"),
    Path("app/db"),
    Path("app/services"),
)


def get_sample_value(metric, sample_name: str, labels: dict[str, str]) -> float:
    for metric_family in metric.collect():
        for sample in metric_family.samples:
            if sample.name == sample_name and sample.labels == labels:
                return sample.value

    return 0.0


def test_logging_processor_removes_raw_exception_and_stack_inputs():
    sensitive_error = RuntimeError("database-password=secret")

    event = observability_logging.remove_unsafe_exception_details(
        _logger=object(),
        _method_name="error",
        event_dict={
            "event": "test.error",
            "exception_type": "RuntimeError",
            "exc_info": sensitive_error,
            "stack_info": "sensitive stack",
        },
    )

    assert event == {
        "event": "test.error",
        "exception_type": "RuntimeError",
    }
    assert "secret" not in str(event)


def test_unhandled_exception_uses_safe_problem_and_diagnostic_log(monkeypatch):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    register_problem_handlers(test_app)

    logger = Mock()
    exception_metric = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)
    monkeypatch.setattr("app.problem_details.record_app_exception", exception_metric)

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("database-password=secret")

    response = TestClient(test_app, raise_server_exceptions=False).get(
        "/boom?source=test"
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Something went wrong. Please try again later."
    )
    assert response.json()["url"] == "/boom?source=test"
    exception_metric.assert_called_once_with("unhandled")
    logger.error.assert_called_once()
    log_fields = logger.error.call_args.kwargs
    assert log_fields["status_code"] == 500
    assert log_fields["exception_type"] == "RuntimeError"
    assert log_fields["problem_type"] == (
        "urn:spend-analyzer:problem:internal-server-error"
    )
    assert "secret" not in str(logger.error.call_args)


def test_application_packages_do_not_import_opentelemetry():
    violations = []

    for package_path in APPLICATION_PACKAGE_PATHS:
        for source_path in package_path.rglob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported_modules = [node.module or ""]
                else:
                    continue

                if any(
                    module == "opentelemetry"
                    or module.startswith("opentelemetry.")
                    for module in imported_modules
                ):
                    violations.append(str(source_path))

    assert violations == []


def test_configure_http_metrics_rejects_route_collision():
    app = FastAPI()

    @app.get("/metrics")
    def existing_metrics_route():
        return {"status": "existing"}

    try:
        metrics.configure_http_metrics(
            app,
            enabled=True,
            metrics_path="/metrics",
        )
    except ValueError as error:
        assert "conflicts with an existing application route" in str(error)
    else:
        raise AssertionError("Expected metrics-path collision to fail")


def test_bounded_auth_and_storage_metrics_increment():
    auth_labels = {"failure_category": "unit_test_invalid_token"}
    storage_labels = {"failure_category": "unit_test_storage_error"}

    auth_before = get_sample_value(
        metrics.AUTH_FAILURES_TOTAL,
        "auth_failures_total",
        auth_labels,
    )
    storage_before = get_sample_value(
        metrics.FILE_STORAGE_FAILURES_TOTAL,
        "file_storage_failures_total",
        storage_labels,
    )

    metrics.record_auth_failure(auth_labels["failure_category"])
    metrics.record_file_storage_failure(storage_labels["failure_category"])

    assert (
        get_sample_value(
            metrics.AUTH_FAILURES_TOTAL,
            "auth_failures_total",
            auth_labels,
        )
        == auth_before + 1
    )
    assert (
        get_sample_value(
            metrics.FILE_STORAGE_FAILURES_TOTAL,
            "file_storage_failures_total",
            storage_labels,
        )
        == storage_before + 1
    )
