# Observability Low-Level Design

## Purpose

This document defines the implementation-level observability design for Spend Analyzer. Operational commands remain in `LOCAL_OBSERVABILITY.md`.

Issue #72 created the shared logging, metrics, tracing, correlation, and local infrastructure. Issue #78 audits existing flows and completes feature-level coverage without adding another observability framework.

## Application wiring

`app/main.py`:

1. configures structured logging;
2. creates FastAPI with a lifespan context;
3. adds request-context middleware;
4. registers RFC 9457 handlers;
5. configures tracing;
6. registers business routers;
7. registers the metrics endpoint last.

This preserves request and trace context and excludes `/metrics` from request logs, HTTP self-metrics, and traces.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `app/http.py` | Relative request URL and request-ID header |
| `app/problem_details.py` | RFC 9457 response construction and handlers |
| `app/observability/context.py` | Request, trace, and span context |
| `app/observability/logging.py` | JSON logging and safe rendering |
| `app/observability/middleware.py` | Request ID, duration, HTTP outcome log, safe 500 response |
| `app/observability/metrics.py` | HTTP and application metrics |
| `app/observability/tracing.py` | Tracing configuration and safe manual spans |

Business modules use these components directly. Do not add another logging facade, metrics registry, middleware, or tracing provider.

## HTTP request logging

Every response carries `X-Request-ID`. Logs also contain `trace_id` and `span_id` when tracing is active.

The middleware emits one `http.request` outcome log per non-metrics request:

```json
{
  "event": "http.request",
  "method": "GET",
  "url": "/statements/statement-123?page=2",
  "status_code": 200,
  "duration_ms": 12.4,
  "request_id": "request-123"
}
```

`url` is the actual relative path plus optional query string. It excludes scheme, host, port, headers, body, and fragment.

Confidential, credential, authentication, financial-content, and personal-information values must not be designed into path or query parameters. HTTP metrics continue using templated route labels; actual URLs are never metric labels.

## Logging convention

Use the existing `structlog` logger like normal Python logging:

```python
logger.info("Application started", version=settings.app_version)
logger.warning("Database health check failed", exception_type="OperationalError")
logger.error("Unexpected storage failure", exception_type="FileStorageError")
```

A useful log contains:

- a clear human-readable message;
- only the safe fields needed for diagnosis;
- automatic correlation when request-scoped.

Useful fields include operation/stage, dependency, duration, count/size, status code, exception class, and generated statement reference.

Do not log raw exception messages or stack traces by default. They can contain credentials, paths, SQL, bind values, provider payloads, or statement data.

| Level | Use |
|---|---|
| DEBUG | Selected checkpoints that add diagnostic information |
| INFO | Lifecycle, successful business outcomes, expected client rejection |
| WARNING | Handled dependency/infrastructure failure |
| ERROR | Unexpected application/internal failure |

Do not log every function entry and exit.

### Current messages

- `Application started` / `Application stopped`
- `http.request`
- `Database health check failed`
- `Database health check returned an unhealthy result`
- `Authentication failed because credentials were missing`
- `Authentication failed because credentials were invalid`
- `JWKS cache miss; retrieving signing keys`
- `Identity provider key retrieval failed`
- `Identity provider returned an invalid signing-key response`
- `Statement upload content read`
- `Statement ingestion succeeded`
- `Statement ingestion rejected an invalid PDF`
- `Statement ingestion rejected an oversized upload`
- `Statement ingestion failed because file storage is unavailable`
- `Statement ingestion failed because of an unexpected storage error`

## RFC 9457 Problem Details

All application `4xx` and `5xx` responses use `application/problem+json` and contain:

- `type`
- `title`
- `status`
- `detail`
- `instance`
- `request_id`
- `url`

Example:

```json
{
  "type": "urn:spend-analyzer:problem:file-storage-unavailable",
  "title": "File storage unavailable",
  "status": 503,
  "detail": "The uploaded statement could not be stored. Try again later.",
  "instance": "urn:spend-analyzer:request:request-123",
  "request_id": "request-123",
  "url": "/ingest"
}
```

The body request ID matches `X-Request-ID`. Protocol headers such as `WWW-Authenticate` and `Allow` are preserved. Validation errors may add a sanitized `errors` array; raw input values are not returned.

Problem types are stable API contracts and are not derived from exceptions or dynamic values.

## Metrics

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

Labels remain bounded. Never use actual URL, request ID, user ID, statement reference, filename, path, or exception message as a label.

## Tracing

Manual spans disable automatic exception recording and automatic exception-derived status. Safe exception events contain only the exception class.

Current manual spans:

```text
statement.ingestion
database.health_check
identity_provider.jwks_fetch
```

Automatic `requests` tracing is suppressed for the JWKS call because it uses a sanitized manual span and must not create duplicate or uncontrolled identity-provider attributes.

## Flow decision matrix

| Flow | Additional telemetry decision |
|---|---|
| Startup/shutdown | One INFO lifecycle log each |
| Successful `/health` | Baseline HTTP telemetry only |
| Successful `/health/db` | Dependency gauge + manual span; no success log |
| Failed `/health/db` | WARNING diagnostic + failed span + gauge + RFC 9457 503 |
| Successful `/me` | Baseline HTTP telemetry only |
| Missing/invalid credentials | INFO diagnostic + bounded auth metric + RFC 9457 401 |
| Successful authentication | Baseline HTTP telemetry only |
| Cached JWKS | No additional telemetry |
| Remote JWKS success | DEBUG cache-miss + dependency gauge + manual span |
| Remote JWKS failure | WARNING diagnostic + failed span + gauge + RFC 9457 503 |
| Successful ingestion | INFO outcome + DEBUG byte count + metrics + span |
| Invalid PDF | INFO diagnostic + failure metric + failed span + RFC 9457 400 |
| Oversized upload | INFO diagnostic + failure metric + failed span + RFC 9457 413 |
| Storage unavailable | WARNING diagnostic + storage/ingestion metrics + failed span + RFC 9457 503 |
| Internal storage error | ERROR diagnostic + storage/ingestion metrics + failed span + RFC 9457 500 |
| Internal helpers | No direct telemetry; caller boundary owns it |
| `/metrics` | Excluded from request logs, HTTP metrics, and traces |

## Bounded categories

Authentication metrics:

```text
missing_credentials
credentials_invalid
```

Statement ingestion metrics/span attributes:

```text
invalid_pdf
upload_too_large
storage_unavailable
storage_internal_error
```

Storage metrics:

```text
unavailable
internal_error
```

Categories support aggregation. Human-readable logs provide diagnostic context.

## Security exclusions

Do not expose in logs, metrics, traces, or Problem Details:

- passwords, API keys, tokens, authorization headers, or claims;
- raw user IDs, usernames, or email addresses;
- database URLs, credentials, SQL, or bind values;
- identity-provider URLs or payloads;
- original filenames when sensitive;
- statement content, extracted text, account/card numbers;
- raw exception messages or stack traces.

Generated request IDs and statement references, counts, sizes, durations, configured limits, status codes, bounded categories, and exception class names are allowed when operationally useful.
