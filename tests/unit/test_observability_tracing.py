import re
from unittest.mock import Mock

from fastapi import FastAPI
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.trace import Status, StatusCode

from app.observability import tracing
from app.observability.tracing import (
    SanitizingSpanProcessor,
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


def test_sanitizing_processor_cleans_span_before_delegate():
    delegate = Mock()
    processor = SanitizingSpanProcessor(delegate)
    unsafe_url = (
        "https://span-user:span-password@api.example.com:8443/"
        "items/private?page=2"
    )
    span = ReadableSpan(
        name="GET /items/{item_id}",
        resource=Resource.create({}),
        attributes={
            "http.route": "/items/{item_id}",
            "http.url": unsafe_url,
            "url.full": unsafe_url,
            "http.target": "/items/private?page=2",
            "url.path": "/items/private",
            "url.query": "page=2&filter=private",
        },
        events=(
            Event(
                "exception",
                attributes={
                    "exception.type": "RuntimeError",
                    "exception.message": "postgresql://user:password@host/private",
                    "exception.stacktrace": "internal stack",
                },
            ),
        ),
        status=Status(StatusCode.ERROR, "internal detail"),
    )

    processor.on_end(span)

    exported_span = delegate.on_end.call_args.args[0]
    expected_url = (
        "https://api.example.com:8443/items/{item_id}"
        "?page=%5BREDACTED%5D&filter=%5BREDACTED%5D"
    )
    assert exported_span.attributes["http.url"] == expected_url
    assert exported_span.attributes["url.full"] == expected_url
    assert exported_span.attributes["http.target"] == (
        "/items/{item_id}?page=%5BREDACTED%5D&filter=%5BREDACTED%5D"
    )
    assert exported_span.attributes["url.path"] == "/items/{item_id}"
    assert dict(exported_span.events[0].attributes) == {
        "exception.type": "RuntimeError"
    }
    assert exported_span.status.status_code is StatusCode.ERROR
    assert exported_span.status.description is None
    assert "span-user" not in str(exported_span.attributes)
    assert "span-password" not in str(exported_span.attributes)
    assert "password" not in str(exported_span.events)


def test_sanitizing_processor_delegates_lifecycle_calls():
    delegate = Mock()
    delegate.force_flush.return_value = True
    processor = SanitizingSpanProcessor(delegate)
    span = Mock()
    parent_context = object()

    processor.on_start(span, parent_context=parent_context)
    assert processor.force_flush(1000) is True
    processor.shutdown()

    delegate.on_start.assert_called_once_with(span, parent_context=parent_context)
    delegate.force_flush.assert_called_once_with(1000)
    delegate.shutdown.assert_called_once_with()


def test_server_hook_replaces_path_and_query_values():
    app = FastAPI()

    @app.get("/items/{item_id}")
    def read_item(item_id: str):
        return {"item_id": item_id}

    span = Mock()
    span.is_recording.return_value = True
    scope = {
        "type": "http",
        "app": app,
        "method": "GET",
        "path": "/items/private-item",
        "query_string": b"source=secret",
        "headers": [],
    }

    tracing._set_server_span_attributes(span, scope)

    attributes = dict(call.args for call in span.set_attribute.call_args_list)
    assert attributes["http.route"] == "/items/{item_id}"
    assert attributes["http.target"] == ("/items/{item_id}?source=%5BREDACTED%5D")
    assert attributes["url.path"] == "/items/{item_id}"
    assert attributes["url.query"] == "source=%5BREDACTED%5D"
    assert "private-item" not in str(attributes)
    assert "secret" not in str(attributes)


def test_client_hook_removes_credentials_path_and_query_values():
    span = Mock()
    span.is_recording.return_value = True
    request = Mock()
    request.url = "https://user:password@api.example.com/private/path?token=secret"

    tracing._set_client_span_attributes(span, request)

    attributes = dict(call.args for call in span.set_attribute.call_args_list)
    assert attributes["url.full"] == (
        "https://api.example.com/<redacted>?token=%5BREDACTED%5D"
    )
    assert attributes["url.path"] == "/<redacted>"
    assert attributes["url.query"] == "token=%5BREDACTED%5D"
    assert "password" not in str(attributes)
    assert "secret" not in str(attributes)


def test_configure_tracing_instruments_safe_http_boundaries(monkeypatch):
    app = FastAPI()
    resource = object()
    sampler = object()
    provider = Mock()
    otlp_exporter = Mock()
    batch_processor = Mock()

    create_resource = Mock(return_value=resource)
    create_sampler = Mock(return_value=sampler)
    create_provider = Mock(return_value=provider)
    create_exporter = Mock(return_value=otlp_exporter)
    create_batch_processor = Mock(return_value=batch_processor)
    instrument_app = Mock()
    requests_instance = Mock()
    create_requests_instrumentor = Mock(return_value=requests_instance)
    set_provider = Mock()

    monkeypatch.setattr(tracing.Resource, "create", create_resource)
    monkeypatch.setattr(tracing, "TraceIdRatioBased", create_sampler)
    monkeypatch.setattr(tracing, "TracerProvider", create_provider)
    monkeypatch.setattr(tracing, "OTLPSpanExporter", create_exporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", create_batch_processor)
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
    create_batch_processor.assert_called_once_with(otlp_exporter)
    safe_processor = provider.add_span_processor.call_args.args[0]
    assert isinstance(safe_processor, SanitizingSpanProcessor)
    assert safe_processor.delegate is batch_processor
    set_provider.assert_called_once_with(provider)

    fastapi_kwargs = instrument_app.call_args.kwargs
    assert fastapi_kwargs["excluded_urls"] == "/metrics"
    assert fastapi_kwargs["server_request_hook"] is tracing._set_server_span_attributes
    assert isinstance(fastapi_kwargs["meter_provider"], NoOpMeterProvider)

    request_kwargs = requests_instance.instrument.call_args.kwargs
    assert request_kwargs["request_hook"] is tracing._set_client_span_attributes
    assert re.search(
        request_kwargs["excluded_urls"],
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
    monkeypatch.setattr(tracing, "BatchSpanProcessor", Mock(return_value=Mock()))
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
    requests_instance.instrument.assert_called_once()
