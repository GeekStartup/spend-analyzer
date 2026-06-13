from fastapi import FastAPI

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
