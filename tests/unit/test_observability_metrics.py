from fastapi import FastAPI
from starlette.routing import Route

from app.observability import metrics


def get_sample_value(metric, sample_name: str, labels: dict[str, str]) -> float:
    for metric_family in metric.collect():
        for sample in metric_family.samples:
            if sample.name == sample_name and sample.labels == labels:
                return sample.value

    return 0.0


def test_configure_http_metrics_does_nothing_when_disabled(monkeypatch):
    app = FastAPI()

    class FailingInstrumentator:
        def __init__(self, **kwargs):
            raise AssertionError("Instrumentator should not be created")

    monkeypatch.setattr(metrics, "Instrumentator", FailingInstrumentator)

    metrics.configure_http_metrics(
        app,
        enabled=False,
        metrics_path="/metrics",
    )

    route_paths = {route.path for route in app.routes if isinstance(route, Route)}

    assert "/metrics" not in route_paths


def test_configure_http_metrics_exposes_metrics_route_when_enabled(monkeypatch):
    app = FastAPI()
    calls = {}

    class FakeInstrumentator:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def instrument(self, instrumented_app):
            calls["instrumented_app"] = instrumented_app
            return self

        def expose(self, exposed_app, *, endpoint, include_in_schema):
            calls["exposed_app"] = exposed_app
            calls["endpoint"] = endpoint
            calls["include_in_schema"] = include_in_schema

            @exposed_app.get(endpoint, include_in_schema=include_in_schema)
            def fake_metrics():
                return "metrics"

            return self

    monkeypatch.setattr(metrics, "Instrumentator", FakeInstrumentator)

    metrics.configure_http_metrics(
        app,
        enabled=True,
        metrics_path="/metrics",
    )

    route_paths = {route.path for route in app.routes if isinstance(route, Route)}

    assert "/metrics" in route_paths
    assert calls["kwargs"] == {
        "should_group_status_codes": True,
        "should_ignore_untemplated": True,
        "excluded_handlers": ["/metrics"],
    }
    assert calls["instrumented_app"] is app
    assert calls["exposed_app"] is app
    assert calls["endpoint"] == "/metrics"
    assert calls["include_in_schema"] is False


def test_record_app_exception_records_exception_category():
    labels = {"exception_category": "unit_test_exception"}

    before = get_sample_value(
        metrics.APP_EXCEPTIONS_TOTAL,
        "app_exceptions_total",
        labels,
    )

    metrics.record_app_exception("unit_test_exception")

    after = get_sample_value(
        metrics.APP_EXCEPTIONS_TOTAL,
        "app_exceptions_total",
        labels,
    )

    assert after == before + 1


def test_record_dependency_health_sets_gauge():
    labels = {"dependency": "unit_test_database"}

    metrics.record_dependency_health("unit_test_database", True)

    assert (
        get_sample_value(
            metrics.APP_DEPENDENCY_HEALTH_STATUS,
            "app_dependency_health_status",
            labels,
        )
        == 1
    )

    metrics.record_dependency_health("unit_test_database", False)

    assert (
        get_sample_value(
            metrics.APP_DEPENDENCY_HEALTH_STATUS,
            "app_dependency_health_status",
            labels,
        )
        == 0
    )


def test_record_statement_ingestion_metrics():
    content_type_labels = {"content_type": "application/unit-test-pdf"}
    failure_labels = {"failure_category": "unit_test_failure"}

    before_attempts = get_sample_value(
        metrics.STATEMENT_INGESTION_ATTEMPTS_TOTAL,
        "statement_ingestion_attempts_total",
        {},
    )
    before_success = get_sample_value(
        metrics.STATEMENT_INGESTION_SUCCESS_TOTAL,
        "statement_ingestion_success_total",
        content_type_labels,
    )
    before_failure = get_sample_value(
        metrics.STATEMENT_INGESTION_FAILURES_TOTAL,
        "statement_ingestion_failures_total",
        failure_labels,
    )
    before_size_count = get_sample_value(
        metrics.STATEMENT_UPLOAD_SIZE_BYTES,
        "statement_upload_size_bytes_count",
        content_type_labels,
    )

    metrics.record_statement_ingestion_attempt()
    metrics.record_statement_ingestion_success(
        content_type="application/unit-test-pdf",
        file_size_bytes=1024,
    )
    metrics.record_statement_ingestion_failure("unit_test_failure")

    after_attempts = get_sample_value(
        metrics.STATEMENT_INGESTION_ATTEMPTS_TOTAL,
        "statement_ingestion_attempts_total",
        {},
    )
    after_success = get_sample_value(
        metrics.STATEMENT_INGESTION_SUCCESS_TOTAL,
        "statement_ingestion_success_total",
        content_type_labels,
    )
    after_failure = get_sample_value(
        metrics.STATEMENT_INGESTION_FAILURES_TOTAL,
        "statement_ingestion_failures_total",
        failure_labels,
    )
    after_size_count = get_sample_value(
        metrics.STATEMENT_UPLOAD_SIZE_BYTES,
        "statement_upload_size_bytes_count",
        content_type_labels,
    )

    assert after_attempts == before_attempts + 1
    assert after_success == before_success + 1
    assert after_failure == before_failure + 1
    assert after_size_count == before_size_count + 1
