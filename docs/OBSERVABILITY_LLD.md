# Observability Low-Level Design

## Purpose

This document defines the implementation-level observability decisions for the current Spend Analyzer application flows. Operational commands are documented in `LOCAL_OBSERVABILITY.md`.

## Tracing decision

Issue #78 uses automatic infrastructure tracing only:

- incoming FastAPI requests are traced by `FastAPIInstrumentor`;
- supported outbound HTTP calls are traced by `RequestsInstrumentor`;
- configured identity-provider issuer and JWKS endpoints are excluded from generic outbound tracing;
- application routes and services do not import OpenTelemetry or create manual spans;
- custom business and dependency spans are deferred to separate work.

The application configures one tracing provider. Completed spans pass through a sanitizing span processor before batching and OTLP export.

The sanitization boundary removes or replaces:

- concrete path values;
- query parameter values;
- credentials embedded in URLs;
- raw exception messages;
- exception stack traces;
- uncontrolled span-status descriptions.

Database health uses the automatic incoming request trace plus a bounded database dependency gauge. Dedicated Psycopg instrumentation requires separate dependency and integration validation.

## Request correlation and HTTP outcome logging

The request-context middleware owns:

- `request_id` validation, generation, and propagation;
- one `http.request` outcome log per non-metrics request;
- automatic HTTP status and duration fields;
- the safe request target used by request logs and Problem Details;
- containment of otherwise unhandled exceptions before they escape to server logging.

Ambient structlog context contains correlation identifiers only. Request targets are event-local data and are not bound to every application log.

The safe request target contract is:

- resolved route template instead of concrete dynamic path values;
- retained query parameter names when safe and bounded;
- `[REDACTED]` for every query parameter value;
- no scheme, host, port, fragment, headers, or request body.

Examples:

```text
/items/{item_id}
/items/{item_id}?source=%5BREDACTED%5D
/<unmatched>?source=%5BREDACTED%5D
```

Logging policy:

- `2xx` request outcomes are INFO;
- `4xx` and `5xx` request outcomes are ERROR;
- controlled failure diagnostics are logged centrally;
- request start and request completion events are not emitted separately.

HTTP metrics continue using bounded route templates and never use the request-target value as a label.

## Error handling and Problem Details

Application code raises typed `ApplicationError` subclasses. Central handlers own:

- stable RFC 9457-compatible problem mapping;
- safe client-facing details;
- protocol headers such as `WWW-Authenticate` and `Allow`;
- sanitized validation errors;
- the final diagnostic error log;
- generic handling for unexpected exceptions.

Every problem response contains:

```text
type
title
status
detail
instance
request_id
url
```

`instance` identifies the occurrence using the request ID. The `X-Request-ID` response header matches the body extension.

Framework `HTTPException.detail`, raw Pydantic input values, raw exception messages, and stack traces are not copied into responses.

## Flow-decision matrix

| Flow | Observability decision |
|---|---|
| Application startup | One structured lifecycle log; no metric or custom span |
| Application shutdown | One structured lifecycle log; no metric or custom span |
| Generic HTTP request | One outcome log, automatic server span, bounded HTTP metrics |
| Successful `/health` | Baseline HTTP telemetry only |
| Successful `/health/db` | Baseline HTTP telemetry plus database dependency gauge |
| Failed `/health/db` | Problem Details 503, centralized diagnostic, dependency gauge |
| Successful `/me` | Baseline HTTP telemetry only |
| Missing credentials | Problem Details 401 plus bounded auth-failure metric |
| Invalid credentials | Problem Details 401 plus bounded auth-failure metric |
| Successful authentication | Baseline HTTP telemetry only |
| Cached JWKS lookup | No additional telemetry |
| Successful JWKS network fetch | Identity-provider dependency gauge; provider endpoint excluded from generic outbound tracing |
| Failed or unusable JWKS response | Problem Details 503, centralized diagnostic, dependency gauge; no invalid-credential metric |
| Successful statement ingestion | Structured business outcome plus bounded ingestion metrics |
| Invalid PDF | Problem Details 400, bounded failure metric, centralized diagnostic |
| Upload too large | Problem Details 413, bounded failure metric, centralized diagnostic |
| File storage unavailable | Problem Details 503, storage and ingestion metrics, centralized diagnostic |
| Internal storage failure | Safe Problem Details 500, bounded storage and ingestion metrics, centralized diagnostic |
| Database connection helper | No direct telemetry; caller boundary owns observability |
| Upload/storage helper | No direct telemetry unless it becomes a reusable external dependency boundary |
| `/metrics` | Excluded from request logs, HTTP metrics, and traces |

## Identity-provider boundary

JWKS access is treated as an external dependency rather than an authentication failure.

Bounded failure categories:

```text
request_failed
invalid_response
```

A JWKS document is usable only when it contains at least one supported RSA signing key with the required key material.

Safe dependency context may contain:

- dependency name;
- operation name;
- bounded failure category;
- exception class name;
- configured timeout.

It must not contain:

- issuer or JWKS URL;
- token or authorization header;
- key ID;
- provider payload;
- raw exception message.

Identity-provider unavailability returns 503 and does not increment `auth_failures_total`.

## Ingestion and storage taxonomy

Statement-ingestion failure categories:

```text
invalid_pdf
upload_too_large
storage_unavailable
storage_internal_error
```

File-storage failure categories:

```text
unavailable
internal_error
```

Typed exceptions distinguish invalid client input, unavailable storage, and internal storage defects. The centralized handler maps each boundary to a stable problem type and safe response.

## Logging guidance

Use the existing structured logger directly:

```python
logger.info("Statement ingestion succeeded", file_size_bytes=file_size_bytes)
logger.debug("Statement upload content read", file_size_bytes=file_size_bytes)
```

Request ID, trace ID, span ID, HTTP status, and duration are supplied by common infrastructure where applicable. Application code should not calculate request duration or import tracing APIs.

Do not log every function entry and exit.

## Metrics and safety

Metric labels must be bounded. Never use:

- actual request targets;
- request, trace, or span IDs;
- user IDs;
- statement references;
- filenames;
- exception messages;
- arbitrary institution or account values.

Do not expose passwords, API keys, bearer values, authorization headers, identity claims, raw user identities, database connection strings, SQL, statement contents, provider payloads, or uncontrolled exception text in logs, metrics, traces, or error responses.

## Testing requirements

Observability tests must verify both behavior and data exclusion:

- one request outcome log;
- status and duration supplied automatically;
- route templates and redacted query values;
- request-ID consistency across logs, headers, and Problem Details;
- controlled framework and validation messages;
- exception containment;
- bounded metrics;
- sanitized span attributes, events, and status;
- absence of credentials, path values, query values, raw exceptions, and stack traces.

CI enforces at least 95% line coverage and 95% branch coverage.
