# Observability Low-Level Design

## Issue #78 tracing decision

Issue #78 uses automatic infrastructure tracing only:

- FastAPI incoming requests are traced by `FastAPIInstrumentor`.
- Outbound HTTP calls are traced by `RequestsInstrumentor`.
- Trace and span identifiers are added to request-scoped structured logs.
- Application modules do not import OpenTelemetry or manually manage spans.
- Custom business spans are deferred to separate work.

Database health uses baseline HTTP tracing plus the bounded database dependency gauge. Dedicated Psycopg automatic instrumentation requires a separate dependency and integration validation.

## Request correlation

The request-context middleware owns:

- `request_id` generation and propagation;
- relative `url` context containing path and query string, without host;
- HTTP status and duration logging;
- INFO outcome logs for successful responses;
- ERROR outcome logs for `4xx` and `5xx` responses.

HTTP metrics continue using bounded route templates rather than actual URLs.

## Error handling

Application code raises typed `ApplicationError` subclasses. Central handlers own:

- stable RFC 9457 problem mapping;
- safe client responses;
- the final diagnostic error log;
- generic handling for otherwise unhandled exceptions.

Every problem response includes `type`, `title`, `status`, `detail`, `instance`, `request_id`, and `url`, and preserves protocol headers such as `WWW-Authenticate` and `Allow`.

## Flow decisions

| Flow | Decision |
|---|---|
| Startup and shutdown | One structured lifecycle log each |
| Successful `/health` | Baseline HTTP telemetry only |
| Successful `/health/db` | HTTP telemetry plus database dependency gauge |
| Failed `/health/db` | Centralized error log, dependency gauge, Problem Details 503 |
| Successful `/me` | Baseline HTTP telemetry only |
| Authentication failure | Bounded auth metric, centralized error log, Problem Details 401 |
| Cached JWKS | No additional telemetry |
| JWKS network request | Dependency gauge plus automatic outbound HTTP tracing |
| Successful ingestion | Structured business outcome plus bounded metrics |
| Ingestion or storage failure | Typed exception, bounded metrics, centralized error log and Problem Details |
| `/metrics` | Excluded from request logs, HTTP metrics, and traces |

## Logging guidance

Use the existing structured logger directly:

```python
logger.info("Statement ingestion succeeded", file_size_bytes=file_size_bytes)
logger.debug("Statement upload content read", file_size_bytes=file_size_bytes)
```

Request URL, request ID, trace ID, span ID, status, and duration are supplied by common infrastructure where applicable. Do not log every function entry and exit.

## Metrics and safety

Metric labels must remain bounded. Never use actual URLs, request IDs, user IDs, statement references, filenames, paths, or exception messages as labels.

Do not expose passwords, API keys, bearer values, authorization headers, identity claims, raw user identities, database connection strings, SQL, statement contents, provider payloads, or uncontrolled exception text in telemetry or error responses.
