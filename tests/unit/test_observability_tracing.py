from unittest.mock import Mock

from fastapi import FastAPI

from app.observability import tracing
from app.observability.tracing import configure_tracing, is_otlp_insecure_endpoint


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


def test_configure_tracing_instruments_http_boundaries(monkeypatch):
    app = FastAPI()
    resource = object()
    sampler = object()
    provider = Mock()
    exporter = object()
    processor = object()

    create_resource = Mock(return_value=resource)
    create_sampler = Mock(return_value=sampler)
    create_provider = Mock(return_value=provider)
    create_exporter = Mock(return_value=exporter)
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
    )

    create_resource.assert_called_once_with({tracing.SERVICE_NAME: "service"})
    create_sampler.assert_called_once_with(0.5)
    create_provider.assert_called_once_with(resource=resource, sampler=sampler)
    create_exporter.assert_called_once_with(
        endpoint="http://localhost:4317",
        insecure=True,
    )
    create_processor.assert_called_once_with(exporter)
    provider.add_span_processor.assert_called_once_with(processor)
    set_provider.assert_called_once_with(provider)
    instrument_app.assert_called_once_with(app, excluded_urls="/metrics")
    requests_instance.instrument.assert_called_once_with()
