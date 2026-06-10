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

## Metrics design

HTTP instrumentation provides request count, grouped status, request and response size, and request duration using route templates.

Custom metrics:

| Metric | Type | Labels |
|---|---|---|
| `app_exceptions_total` | Counter | `exception_category` |
| `app_dependency_health_status` | Gauge | `dependency` |
| `auth_failures_total` | Counter | `failure_category` |
| `file_storage_failures_total` | Counter | `failure_category` |
| `statement_ingestion_attempts_total` | Counter | none |
| `statement_ingestion_success_total` | Counter | `content_type` |
| `statement_ingestion_failures_total` | Counter | `failure_category` |
| `statement_upload_size_bytes` | Histogram | `content_type` |

Metric labels remain bounded. Correlation identifiers, user identifiers, statement references, filenames, paths, and exception messages are not metric labels. Upload-size histogram buckets are expressed in bytes.

## Tracing design

Tracing uses an OpenTelemetry provider, service resource attributes, ratio-based sampling, batch processing, OTLP/gRPC export, FastAPI instrumentation, and outbound `requests` instrumentation.

Manual spans disable automatic exception capture and automatic error status. The safe exception helper records only the exception class name.

Current manual spans:

```text
statement.ingestion
database.health_check
```

## Authentication observability

Bounded authentication failure categories are:

```text
missing_credentials
credentials_invalid
```

Failures return 401 and increment `auth_failures_total`. Authentication material, validation messages, issuers, and identity fields are excluded from telemetry. Successful `/me` requests use baseline HTTP telemetry only.

## Database-health observability

`GET /health/db` creates `database.health_check` and updates the database dependency gauge.

Success:

- HTTP 200;
- gauge value `1`;
- span outcome `healthy`;
- no per-probe success event.

Failure:

- HTTP 503;
- gauge value `0`;
- error span status;
- bounded category `connection_error` or `health_check_failed`;
- safe warning event;
- exception class event for database-driver failures.

Connection details, query text, bind values, host details, and raw exception messages are excluded.

## Statement-ingestion observability

The attempt counter increments before validation, and the route creates `statement.ingestion`.

Success records normalized content type, file size, success counter, upload-size observation, succeeded span outcome, and a safe business event.

Bounded failures:

| Category | Meaning | Status |
|---|---|---:|
| `upload_too_large` | Configured size exceeded | 413 |
| `file_validation_or_storage` | Invalid input or validation failure | 400 |
| `storage_error` | Filesystem unavailable | 503 |

A storage failure also increments `file_storage_failures_total`. Ingestion telemetry excludes original filenames, user identifiers, optional metadata hints, PDF content, and raw exception text.

## File-storage boundary

The storage service translates filesystem failures into `FileStorageUnavailableError`. This prevents operating-system details from being exposed, distinguishes invalid input from unavailable storage, and allows the route to return 503 and update both ingestion and storage metrics. Blocking writes run in a thread pool.
