import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import (
    Event,
    ReadableSpan,
    Span,
    SpanProcessor,
    TracerProvider,
)
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Status

from app.http import (
    REDACTED_PATH,
    UNMATCHED_ROUTE_PATH,
    get_safe_relative_url_from_scope,
    resolve_route_template,
    sanitize_query_string,
    sanitize_url,
)

_URL_ATTRIBUTE_KEYS = {"http.url", "url.full"}
_TARGET_ATTRIBUTE_KEYS = {"http.target"}
_PATH_ATTRIBUTE_KEYS = {"url.path"}
_QUERY_ATTRIBUTE_KEYS = {"url.query"}
_EXCEPTION_EVENT_NAME = "exception"
_EXCEPTION_TYPE_ATTRIBUTE = "exception.type"


def is_otlp_insecure_endpoint(otlp_endpoint: str) -> bool:
    return not otlp_endpoint.lower().startswith("https://")


def build_excluded_url_pattern(urls: Sequence[str]) -> str | None:
    """Build exact-match patterns for endpoints that must not enter traces."""
    patterns = [rf"^{re.escape(url)}(?:\?.*)?$" for url in urls if url]
    return "|".join(patterns) if patterns else None


def _sanitize_event(event: Event) -> Event:
    if event.name != _EXCEPTION_EVENT_NAME:
        return event

    event_attributes = event.attributes or {}
    exception_type = event_attributes.get(_EXCEPTION_TYPE_ATTRIBUTE)
    attributes = (
        {_EXCEPTION_TYPE_ATTRIBUTE: exception_type}
        if isinstance(exception_type, str)
        else None
    )
    return Event(
        name=event.name,
        attributes=attributes,
        timestamp=event.timestamp,
    )


def _safe_full_url(value: str, safe_path: str, safe_query: str) -> str:
    sanitized = urlsplit(sanitize_url(value))
    return urlunsplit(
        (
            sanitized.scheme,
            sanitized.netloc,
            safe_path,
            safe_query,
            "",
        )
    )


def _sanitize_span(span: ReadableSpan) -> ReadableSpan:
    attributes: dict[str, Any] = dict(span.attributes or {})
    route = attributes.get("http.route")
    safe_path = route if isinstance(route, str) else REDACTED_PATH

    raw_query = attributes.get("url.query")
    safe_query = sanitize_query_string(raw_query) if isinstance(raw_query, str) else ""
    safe_target = f"{safe_path}?{safe_query}" if safe_query else safe_path

    for key in _URL_ATTRIBUTE_KEYS:
        value = attributes.get(key)
        if isinstance(value, str):
            attributes[key] = (
                _safe_full_url(value, safe_path, safe_query)
                if isinstance(route, str)
                else sanitize_url(value)
            )

    for key in _TARGET_ATTRIBUTE_KEYS:
        if key in attributes:
            attributes[key] = safe_target

    for key in _PATH_ATTRIBUTE_KEYS:
        if key in attributes:
            attributes[key] = safe_path

    for key in _QUERY_ATTRIBUTE_KEYS:
        if key in attributes:
            attributes[key] = safe_query

    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        events=tuple(_sanitize_event(event) for event in span.events),
        links=span.links,
        kind=span.kind,
        status=Status(span.status.status_code),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class SanitizingSpanProcessor(SpanProcessor):
    """Sanitize completed spans before they enter batching or export."""

    def __init__(self, delegate: SpanProcessor) -> None:
        self.delegate = delegate

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        self.delegate.on_start(span, parent_context=parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        self.delegate.on_end(_sanitize_span(span))

    def shutdown(self) -> None:
        self.delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.delegate.force_flush(timeout_millis)


def _set_server_span_attributes(span: Any, scope: Mapping[str, Any]) -> None:
    if not span.is_recording():
        return

    route = resolve_route_template(scope) or UNMATCHED_ROUTE_PATH
    safe_relative_url = get_safe_relative_url_from_scope(scope)
    raw_query = scope.get("query_string", b"")
    query = (
        raw_query.decode("utf-8", errors="replace")
        if isinstance(raw_query, bytes)
        else str(raw_query)
    )
    safe_query = sanitize_query_string(query)

    span.set_attribute("http.route", route)
    span.set_attribute("http.target", safe_relative_url)
    span.set_attribute("http.url", safe_relative_url)
    span.set_attribute("url.full", safe_relative_url)
    span.set_attribute("url.path", route)
    span.set_attribute("url.query", safe_query)


def _set_client_span_attributes(span: Any, request: Any) -> None:
    if not span.is_recording():
        return

    raw_url = getattr(request, "url", None)
    if not isinstance(raw_url, str):
        return

    safe_url = sanitize_url(raw_url)
    parsed = urlsplit(safe_url)
    span.set_attribute("http.url", safe_url)
    span.set_attribute("url.full", safe_url)
    span.set_attribute("url.path", parsed.path)
    span.set_attribute("url.query", parsed.query)


def configure_tracing(
    app: FastAPI,
    *,
    enabled: bool,
    service_name: str,
    otlp_endpoint: str,
    sample_ratio: float,
    otlp_insecure: bool = True,
    excluded_urls: str | None = None,
    excluded_outbound_urls: Sequence[str] = (),
) -> None:
    """Configure automatic HTTP tracing without application-level span code."""
    if not enabled:
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(sample_ratio),
    )
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=otlp_insecure and is_otlp_insecure_endpoint(otlp_endpoint),
    )
    batch_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(SanitizingSpanProcessor(batch_processor))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=excluded_urls,
        server_request_hook=_set_server_span_attributes,
        meter_provider=NoOpMeterProvider(),
    )
    RequestsInstrumentor().instrument(
        excluded_urls=build_excluded_url_pattern(excluded_outbound_urls),
        request_hook=_set_client_span_attributes,
    )
