from unittest.mock import Mock

from fastapi import FastAPI

from app.observability import tracing


def test_configure_tracing_honours_secure_override(monkeypatch):
    provider = Mock()
    exporter = Mock()
    create_exporter = Mock(return_value=exporter)

    monkeypatch.setattr(tracing.Resource, "create", Mock(return_value=object()))
    monkeypatch.setattr(tracing, "TraceIdRatioBased", Mock(return_value=object()))
    monkeypatch.setattr(tracing, "TracerProvider", Mock(return_value=provider))
    monkeypatch.setattr(tracing, "OTLPSpanExporter", create_exporter)
    monkeypatch.setattr(
        tracing,
        "BatchSpanProcessor",
        Mock(return_value=object()),
    )
    monkeypatch.setattr(tracing.FastAPIInstrumentor, "instrument_app", Mock())
    requests_instance = Mock()
    monkeypatch.setattr(
        tracing,
        "RequestsInstrumentor",
        Mock(return_value=requests_instance),
    )
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", Mock())

    tracing.configure_tracing(
        FastAPI(),
        enabled=True,
        service_name="service",
        otlp_endpoint="http://localhost:4317",
        sample_ratio=1.0,
        otlp_insecure=False,
    )

    create_exporter.assert_called_once_with(
        endpoint="http://localhost:4317",
        insecure=False,
    )
