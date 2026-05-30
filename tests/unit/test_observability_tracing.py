from fastapi import FastAPI

from app.observability.tracing import (
    configure_tracing,
    disabled_span,
    get_tracer,
    start_span,
)


def test_configure_tracing_does_nothing_when_disabled():
    app = FastAPI()

    configure_tracing(
        app,
        enabled=False,
        service_name="spend-analyzer-api",
        otlp_endpoint="http://localhost:4317",
        sample_ratio=1.0,
    )


def test_get_tracer_returns_tracer():
    tracer = get_tracer()

    assert tracer is not None


def test_start_span_without_attributes():
    with start_span("unit_test_span") as span:
        assert span is not None


def test_start_span_with_attributes():
    with start_span(
        "unit_test_span_with_attributes",
        attributes={
            "app.operation": "unit_test",
            "ignored.none": None,
        },
    ) as span:
        assert span is not None


def test_disabled_span_context_manager():
    with disabled_span() as value:
        assert value is None
