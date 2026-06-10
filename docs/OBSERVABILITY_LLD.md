# Observability Low-Level Design

## Purpose

This document defines the implementation-level observability design for Spend Analyzer. It complements `LLD.md`; operational commands remain in `LOCAL_OBSERVABILITY.md`.

## Application wiring

`app/main.py` configures logging, creates FastAPI, adds request-context middleware, configures tracing, registers business routers, and registers the metrics endpoint last.

This ordering preserves active trace context, prevents metrics-route shadowing, and excludes metric scrapes from request logs, HTTP metrics, and traces. The application remains usable when metrics or tracing are disabled.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `app/observability/context.py` | Request, trace, and span correlation context |
| `app/observability/logging.py` | Structured JSON output and safe rendering |
| `app/observability/middleware.py` | Request ID, duration, outcome event, and safe 500 response |
| `app/observability/metrics.py` | HTTP and custom application metrics |
| `app/observability/tracing.py` | OpenTelemetry configuration and manual span helpers |

Business modules reuse these helpers rather than creating additional middleware, registries, or providers.

## Configuration

```text
LOG_LEVEL
LOG_FORMAT
METRICS_ENABLED
METRICS_PATH
TRACING_ENABLED
OTEL_SERVICE_NAME
OTEL_EXPORTER_OTLP_ENDPOINT
OTEL_SAMPLE_RATIO
```

The metrics path must be a non-root absolute path and must not conflict with an application route. Local Prometheus currently scrapes `/metrics`. Tracing is disabled by default, and the application does not depend on the optional observability profile.

## Request context and logging

Every request accepts an incoming `X-Request-ID` or receives a generated UUID. The identifier is returned on all responses, including generic 500 responses. Active trace and span identifiers are added to logs when tracing is enabled.

The middleware emits one `http.request` outcome-summary event with method, route template, status, duration, and correlation context. Separate request-start and request-completion events are intentionally avoided.

The logging pipeline removes uncontrolled exception and stack inputs before JSON rendering. Application code records bounded failure categories and exception class names.
