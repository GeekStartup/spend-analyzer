from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability import logging as observability_logging
from app.observability import metrics, tracing
from app.observability.middleware import RequestContextMiddleware


def get_sample_value(metric, sample_name: str, labels: dict[str, str]) -> float:
    for metric_family in metric.collect():
        for sample in metric_family.samples:
            if sample.name == sample_name and sample.labels == labels:
                return sample.value

    return 0.0


class EventRecordingSpan:
    def __init__(self):
        self.events = []

    def add_event(self, name, attributes=None):
        self.events.append((name, attributes))


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


def test_record_exception_safely_records_only_exception_type():
    span = EventRecordingSpan()
    sensitive_error = RuntimeError(
        "postgresql://database-user:database-password@database.internal/spend"
    )

    tracing.record_exception_safely(span, sensitive_error)

    assert span.events == [
        (
            tracing.SAFE_EXCEPTION_EVENT_NAME,
            {"exception.type": "RuntimeError"},
        )
    ]
    assert "database-password" not in str(span.events)


def test_unhandled_exception_log_excludes_exception_message(monkeypatch):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    log_calls = []

    monkeypatch.setattr(
        "app.observability.middleware.record_app_exception",
        lambda _category: None,
    )
    monkeypatch.setattr(
        "app.observability.middleware.logger.error",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
    )

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("database-password=secret")

    response = TestClient(test_app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    assert len(log_calls) == 1
    assert log_calls[0][1]["exception_type"] == "RuntimeError"
    assert "secret" not in str(log_calls)


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


def test_start_span_disables_automatic_exception_recording(monkeypatch):
    calls = {}

    class FakeTracer:
        def start_as_current_span(self, name, **kwargs):
            calls["name"] = name
            calls["kwargs"] = kwargs

            class ContextManager:
                def __enter__(self):
                    return object()

                def __exit__(self, exc_type, exc_value, traceback):
                    return None

            return ContextManager()

    monkeypatch.setattr(tracing, "get_tracer", lambda: FakeTracer())

    with tracing.start_span("safe.test"):
        pass

    assert calls == {
        "name": "safe.test",
        "kwargs": {
            "record_exception": False,
            "set_status_on_exception": False,
        },
    }
