from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased


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
    """Configure automatic HTTP tracing without application-level span code."""
    if not enabled:
        return

    resource = Resource.create({SERVICE_NAME: service_name})
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

    FastAPIInstrumentor.instrument_app(app, excluded_urls=excluded_urls)
    RequestsInstrumentor().instrument()
