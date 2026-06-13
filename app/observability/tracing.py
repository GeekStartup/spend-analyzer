import re
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Status

from app.http import sanitize_query_string, sanitize_url

_URL_ATTRIBUTE_KEYS = {"http.url", "url.full"}
_TARGET_ATTRIBUTE_KEYS = {"http.target"}
_QUERY_ATTRIBUTE_KEYS = {"url.query"}
_EXCEPTION_EVENT_NAME = "exception"
_EXCEPTION_TYPE_ATTRIBUTE = "exception.type"


def is_otlp_insecure_endpoint(otlp_endpoint: str) -> bool:
    return not otlp_endpoint.lower().startswith("https://")


def build_excluded_url_pattern(urls: Sequence[str]) -> str | None:
    """Build exact-match patterns for endpoints that must not enter traces."""
    patterns = [rf"{re.escape(url)}(?:\?.*)?$" for url in urls if url]

    if not patterns:
        return None

    return "|".join(patterns)


def _sanitize_event(event: Event) -> Event:
    if event.name != _EXCEPTION_EVENT_NAME:
        return event

    exception_type = event.attributes.get(_EXCEPTION_TYPE_ATTRIBUTE)
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


def _sanitize_span(span: ReadableSpan) -> ReadableSpan:
    attributes: dict[str, Any] = dict(span.attributes)

    for key in _URL_ATTRIBUTE_KEYS | _TARGET_ATTRIBUTE_KEYS:
        value = attributes.get(key)
        if isinstance(value, str):
            attributes[key] = sanitize_url(value)

    for key in _QUERY_ATTRIBUTE_KEYS:
        value = attributes.get(key)
        if isinstance(value, str):
            attributes[key] = sanitize_query_string(value)

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


class SanitizingSpanExporter(SpanExporter):
    """Remove uncontrolled URL values and exception details before export."""

    def __init__(self, delegate: SpanExporter) -> None:
        self.delegate = delegate

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self.delegate.export(tuple(_sanitize_span(span) for span in spans))

    def shutdown(self) -> None:
        self.delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.delegate.force_flush(timeout_millis)


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
    provider.add_span_processor(
        BatchSpanProcessor(SanitizingSpanExporter((otlp_exporter)))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, excluded_urls=excluded_urls)
    RequestsInstrumentor().instrument(
        excluded_urls=build_excluded_url_pattern(excluded_outbound_urls)
    )
