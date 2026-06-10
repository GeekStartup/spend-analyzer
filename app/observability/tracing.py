from contextlib import nullcontext
from types import TracebackType
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Span

TRACER_NAME = "spend-analyzer"
SAFE_EXCEPTION_EVENT_NAME = "exception"


def is_otlp_insecure_endpoint(otlp_endpoint: str) -> bool:
    return not otlp_endpoint.lower().startswith("https://")


def configure_tracing(
    app: FastAPI,
    *,
    enabled: bool,
    service_name: str,
    otlp_endpoint: str,
    sample_ratio: float,
    otlp_insecure: bool = True,
    excluded_urls: str | None = None,
) -> None:
    if not enabled:
        return

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
        }
    )

    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(sample_ratio),
    )

    exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=otlp_insecure and is_otlp_insecure_endpoint(otlp_endpoint),
    )

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=excluded_urls,
    )
    RequestsInstrumentor().instrument()


def get_tracer(name: str = TRACER_NAME):
    return trace.get_tracer(name)


def start_span(name: str, attributes: dict[str, Any] | None = None):
    span_context_manager = get_tracer().start_as_current_span(
        name,
        record_exception=False,
        set_status_on_exception=False,
    )

    if not attributes:
        return span_context_manager

    return SpanAttributeContextManager(span_context_manager, attributes)


def record_exception_safely(span: Span, error: BaseException) -> None:
    """
    Record only the exception class in telemetry.

    Raw exception messages and stack traces can contain credentials,
    filenames, financial content, or third-party response payloads.
    """
    add_event = getattr(span, "add_event", None)

    if callable(add_event):
        add_event(
            SAFE_EXCEPTION_EVENT_NAME,
            attributes={
                "exception.type": error.__class__.__name__,
            },
        )
        return

    # Lightweight test doubles created before this helper may expose only
    # record_exception(). Real OpenTelemetry Span implementations expose
    # add_event(), which is the production path above.
    span.record_exception(error)


def disabled_span():
    return nullcontext()


class SpanAttributeContextManager:
    def __init__(self, span_context_manager, attributes: dict[str, Any]):
        self.span_context_manager = span_context_manager
        self.attributes = attributes

    def __enter__(self) -> Any:
        span = self.span_context_manager.__enter__()

        for key, value in self.attributes.items():
            if value is not None:
                span.set_attribute(key, value)

        return span

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return self.span_context_manager.__exit__(exc_type, exc_value, traceback)
