import re
from unittest.mock import Mock

from fastapi import FastAPI
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import Status, StatusCode

from app.observability import tracing
from app.observability.tracing import (
    SanitizingSpanExporter,
    build_excluded_url_pattern,
    configure_tracing,
    is_otlp_insecure_endpoint,
)


def test_configure_tracing_is_disabled_cleanly():
    configure_tracing(
        FastAPI(),
        enabled=False,
        service_name="service",
        otlp_endpoint="http://localhost:4317",
        sample_ratio=1.0,
    )


def test_otlp_transport_detection():
    assert is_otlp_insecure_endpoint("http://localhost:4317") is True
    assert is_otlp_insecure_endpoint("https://collector.example.com:4317") is False


def test_excluded_url_pattern_matches_only_configured_endpoint():
    pattern = build_excluded_url_pattern(("https://identity.example.com/realm/keys",))

    assert pattern is not None
    assert re.search(pattern, "https://identity.example.com/realm/keys")
    assert re.search(pattern, "https://identity.example.com/realm/keys?cache=false")
    assert not re.search(pattern, "https://identity.example.com/realm/profile")
    assert build_excluded_url_pattern(()) is None


def test_sanitizing_exporter_removes_url_values_and_exception_details():
    delegate = Mock()
    delegate.export.return_value = SpanExportResult.SUCCESS
    exporter = SanitizingSpanExporter(delegate)
    span = ReadableSpan(
        name="GET",
        resource=Resource.create({}),
        attributes={
            "url.full": "https://api.example.com/items?page=2&filter=private",
            "http.target": "/items?page=2",
            "url.query": "page=2&filter=private",
        },
        events=(
            Event(
                "exception",
                attributes={
                    "exception.type": "RuntimeError",
                    "exception.message": "internal detail",
                    "exception.stacktrace": "internal stack",
                },
            ),
        ),
        status=Status(StatusCode.ERROR, "internal detail"),
    )

    result = exporter.export((span,))

    assert result is SpanExportResult.SUCCESS
    exported_span = delegate.export.call_args.args[0][0]
    assert exported_span.attributes["url.full"] == (
        "https://api.example.com/items?page=%5BREDACTED%5D&filter=%5BREDACTED%5D"
    )
    assert exported_span.attributes["http.target"] == ("/items?page=%5BREDACTED%5D")
    assert exported_span.attributes["url.query"] == (
        "page=%5BREDACTED%5D&filter=%5BREDACTED%5D"
    )
    assert dict(exported_span.events[0].attributes) == {
        "exception.type": "RuntimeError"
    }
    assert exported_span.status.status_code is StatusCode.ERROR
    assert exported_span.status.description is None


def test_sanitizing_exporter_delegates_lifecycle_calls():
    delegate = Mock()
    delegate.force_flush.return_value = True
    exporter = SanitizingSpanExporter(delegate)

    assert exporter.force_flush(1000) is True
    exporter.shutdown()

    delegate.force_flush.assert_called_once_with(1000)
    delegate.shutdown.assert_called_once_with()


def test_configure_tracing_instruments_safe_http_boundaries(monkeypatch):
    app = FastAPI()
    resource = object()
    sampler = object()
    provider = Mock()
    otlp_exporter = Mock()
    processor = object()

    create_resource = Mock(return_value=resource)
    create_sampler = Mock(return_value=sampler)
    create_provider = Mock(return_value=provider)
    create_exporter = Mock(return_value=otlp_exporter)
    create_processor = Mock(return_value=processor)
    instrument_app = Mock()
    requests_instance = Mock()
    create_requests_instrumentor = Mock(return_value=requests_instance)
    set_provider = Mock()

    monkeypatch.setattr(tracing.Resource, "create", create_resource)
    monkeypatch.setattr(tracing, "TraceIdRatioBased", create_sampler)
    monkeypatch.setattr(tracing, "TracerProvider", create_provider)
    monkeypatch.setattr(tracing, "OTLPSpanExporter", create_exporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", create_processor)
    monkeypatch.setattr(tracing.FastAPIInstrumentor, "instrument_app", instrument_app)
    monkeypatch.setattr(tracing, "RequestsInstrumentor", create_requests_instrumentor)
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", set_provider)

    configure_tracing(
        app,
        enabled=True,
        service_name="service",
        otlp_endpoint="http://localhost:4317",
        sample_ratio=0.5,
        excluded_urls="/metrics",
        excluded_outbound_urls=("https://identity.example.com/realm/keys",),
    )

    create_resource.assert_called_once_with({tracing.SERVICE_NAME: "service"})
    create_sampler.assert_called_once_with(0.5)
    create_provider.assert_called_once_with(resource=resource, sampler=sampler)
    create_exporter.assert_called_once_with(
        endpoint="http://localhost:4317",
        insecure=True,
    )
    sanitizing_exporter = create_processor.call_args.args[0]
    assert isinstance(sanitizing_exporter, SanitizingSpanExporter)
    assert sanitizing_exporter.delegate is otlp_exporter
    provider.add_span_processor.assert_called_once_with(processor)
    set_provider.assert_called_once_with(provider)
    instrument_app.assert_called_once_with(app, excluded_urls="/metrics")
    excluded_pattern = requests_instance.instrument.call_args.kwargs["excluded_urls"]
    assert re.search(
        excluded_pattern,
        "https://identity.example.com/realm/keys",
    )


def test_configure_tracing_disables_insecure_transport_for_https(monkeypatch):
    provider = Mock()
    create_exporter = Mock(return_value=Mock())
    requests_instance = Mock()

    monkeypatch.setattr(tracing.Resource, "create", Mock(return_value=object()))
    monkeypatch.setattr(tracing, "TraceIdRatioBased", Mock(return_value=object()))
    monkeypatch.setattr(tracing, "TracerProvider", Mock(return_value=provider))
    monkeypatch.setattr(tracing, "OTLPSpanExporter", create_exporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", Mock(return_value=object()))
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", Mock())
    monkeypatch.setattr(tracing.FastAPIInstrumentor, "instrument_app", Mock())
    monkeypatch.setattr(
        tracing,
        "RequestsInstrumentor",
        Mock(return_value=requests_instance),
    )

    configure_tracing(
        FastAPI(),
        enabled=True,
        service_name="service",
        otlp_endpoint="https://collector.example.com:4317",
        sample_ratio=1.0,
    )

    create_exporter.assert_called_once_with(
        endpoint="https://collector.example.com:4317",
        insecure=False,
    )
    requests_instance.instrument.assert_called_once_with(excluded_urls=None)
