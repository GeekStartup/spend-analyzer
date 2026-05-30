from fastapi import FastAPI

from app.observability import tracing
from app.observability.tracing import (
    configure_tracing,
    disabled_span,
    get_tracer,
    is_otlp_insecure_endpoint,
    start_span,
)


def test_configure_tracing_does_nothing_when_disabled():
    app = FastAPI()

    configure_tracing(
        app,
        enabled=False,
        service_name="spend-analyzer-api",
        otlp_endpoint="http://localhost:4317",
        otlp_insecure=True,
        sample_ratio=1.0,
    )


def test_is_otlp_insecure_endpoint_returns_true_for_http_endpoint():
    assert is_otlp_insecure_endpoint("http://localhost:4317") is True


def test_is_otlp_insecure_endpoint_returns_false_for_https_endpoint():
    assert is_otlp_insecure_endpoint("https://collector.example.com:4317") is False


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


def test_configure_tracing_infers_insecure_transport_for_http_endpoint(monkeypatch):
    app = FastAPI()
    calls = {}

    class FakeResource:
        @staticmethod
        def create(attributes):
            calls["resource_attributes"] = attributes
            return "fake-resource"

    class FakeSampler:
        def __init__(self, sample_ratio):
            calls["sample_ratio"] = sample_ratio

    class FakeTracerProvider:
        def __init__(self, *, resource, sampler):
            calls["provider_resource"] = resource
            calls["provider_sampler"] = sampler

        def add_span_processor(self, span_processor):
            calls["span_processor"] = span_processor

    class FakeExporter:
        def __init__(self, *, endpoint, insecure):
            calls["exporter_endpoint"] = endpoint
            calls["exporter_insecure"] = insecure

    class FakeBatchSpanProcessor:
        def __init__(self, exporter):
            calls["batch_exporter"] = exporter

    class FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(instrumented_app, excluded_urls=None):
            calls["fastapi_app"] = instrumented_app
            calls["excluded_urls"] = excluded_urls

    class FakeRequestsInstrumentor:
        def instrument(self):
            calls["requests_instrumented"] = True

    def fake_set_tracer_provider(provider):
        calls["tracer_provider"] = provider

    monkeypatch.setattr(tracing, "Resource", FakeResource)
    monkeypatch.setattr(tracing, "TraceIdRatioBased", FakeSampler)
    monkeypatch.setattr(tracing, "TracerProvider", FakeTracerProvider)
    monkeypatch.setattr(tracing, "OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", FakeBatchSpanProcessor)
    monkeypatch.setattr(tracing, "FastAPIInstrumentor", FakeFastAPIInstrumentor)
    monkeypatch.setattr(tracing, "RequestsInstrumentor", FakeRequestsInstrumentor)
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", fake_set_tracer_provider)

    configure_tracing(
        app,
        enabled=True,
        service_name="spend-analyzer-api",
        otlp_endpoint="http://localhost:4317",
        otlp_insecure=False,
        sample_ratio=0.5,
        excluded_urls="/metrics",
    )

    assert calls["resource_attributes"] == {
        tracing.SERVICE_NAME: "spend-analyzer-api",
    }
    assert calls["sample_ratio"] == 0.5
    assert calls["provider_resource"] == "fake-resource"
    assert calls["exporter_endpoint"] == "http://localhost:4317"
    assert calls["exporter_insecure"] is False
    assert calls["fastapi_app"] is app
    assert calls["excluded_urls"] == "/metrics"
    assert calls["requests_instrumented"] is True
    assert "provider_sampler" in calls
    assert "tracer_provider" in calls
    assert "span_processor" in calls
    assert "batch_exporter" in calls


def test_configure_tracing_allows_explicit_secure_override(monkeypatch):
    app = FastAPI()
    calls = {}

    class FakeResource:
        @staticmethod
        def create(attributes):
            return attributes

    class FakeSampler:
        def __init__(self, sample_ratio):
            pass

    class FakeTracerProvider:
        def __init__(self, *, resource, sampler):
            pass

        def add_span_processor(self, span_processor):
            pass

    class FakeExporter:
        def __init__(self, *, endpoint, insecure):
            calls["exporter_endpoint"] = endpoint
            calls["exporter_insecure"] = insecure

    class FakeBatchSpanProcessor:
        def __init__(self, exporter):
            pass

    class FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(instrumented_app, excluded_urls=None):
            pass

    class FakeRequestsInstrumentor:
        def instrument(self):
            pass

    def fake_set_tracer_provider(provider):
        pass

    monkeypatch.setattr(tracing, "Resource", FakeResource)
    monkeypatch.setattr(tracing, "TraceIdRatioBased", FakeSampler)
    monkeypatch.setattr(tracing, "TracerProvider", FakeTracerProvider)
    monkeypatch.setattr(tracing, "OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", FakeBatchSpanProcessor)
    monkeypatch.setattr(tracing, "FastAPIInstrumentor", FakeFastAPIInstrumentor)
    monkeypatch.setattr(tracing, "RequestsInstrumentor", FakeRequestsInstrumentor)
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", fake_set_tracer_provider)

    configure_tracing(
        app,
        enabled=True,
        service_name="spend-analyzer-api",
        otlp_endpoint="http://localhost:4317",
        sample_ratio=1.0,
        otlp_insecure=False,
    )

    assert calls["exporter_endpoint"] == "http://localhost:4317"
    assert calls["exporter_insecure"] is False
