# Observability Low-Level Design

## Issue #78 decisions

Issue #78 completes observability for existing application flows without requiring application developers to manage OpenTelemetry spans.

### Automatic tracing

- Incoming FastAPI requests are instrumented centrally by `FastAPIInstrumentor`.
- Outbound `requests` calls are instrumented centrally, except configured identity-provider issuer and JWKS endpoints.
- Application modules do not import OpenTelemetry or manually create spans.
- Custom business spans are deferred to separate work.
- Database health uses the incoming HTTP trace plus the bounded dependency-health gauge. Dedicated Psycopg instrumentation is separate work.

Before export, trace telemetry is sanitized:

- query-parameter names may remain, but every value is replaced with `[REDACTED]`;
- exception events retain only `exception.type`;
- exception messages, stack traces, and status descriptions are removed;
- configured identity-provider endpoints are excluded from outbound tracing.

## Request correlation

The request-context middleware owns:

- request-ID validation, generation, and `X-Request-ID` propagation;
- relative URL context without scheme, host, port, or fragment;
- query-parameter value redaction;
- automatic status and duration capture;
- INFO outcome logs for successful responses;
- ERROR outcome logs for `4xx` and `5xx` responses;
- containment of otherwise unexpected exceptions inside the controlled 500 boundary.

HTTP metrics continue using bounded route templates. Actual URLs are never metric labels.

## Error handling

Application code raises typed `ApplicationError` subclasses. Central handlers own:

- stable RFC 9457 problem mapping;
- project-owned client-safe messages;
- the final diagnostic error log;
- generic handling for unanticipated failures.

Problem responses include `type`, `title`, `status`, `detail`, `instance`, `request_id`, and sanitized `url`. Protocol headers such as `WWW-Authenticate` and `Allow` are preserved.

Framework exception details and Pydantic validator messages are not returned directly. Validation error codes are mapped to controlled messages. Application diagnostic context is restricted to an explicit field allowlist and scalar values.

## Flow decisions

| Flow | Decision |
|---|---|
| Startup and shutdown | One structured lifecycle log each |
| Successful `/health` | Baseline HTTP telemetry only |
| Successful `/health/db` | HTTP telemetry plus database dependency gauge |
| Failed `/health/db` | Centralized error log, dependency gauge, Problem Details 503 |
| Successful `/me` | Baseline HTTP telemetry only |
| Missing or invalid credentials | Bounded auth metric, centralized error log, Problem Details 401 |
| Cached JWKS | No additional telemetry |
| JWKS retrieval | Dependency gauge; identity-provider endpoint excluded from traces |
| Malformed JWKS | Dependency failure, Problem Details 503, no auth-failure increment |
| Successful ingestion | Structured business outcome plus bounded metrics |
| Ingestion or storage failure | Typed exception, bounded metrics, centralized error log and Problem Details |
| `/metrics` | Excluded from request logs, HTTP metrics, and traces |

## Logging guidance

Use the existing structured logger directly:

```python
logger.info("Statement ingestion succeeded", file_size_bytes=file_size_bytes)
logger.debug("Statement upload content read", file_size_bytes=file_size_bytes)
```

Request ID, sanitized URL, trace ID, span ID, status, and duration are supplied by common infrastructure where applicable. Do not log every function entry and exit.

## Metrics and safety

Metric labels must remain bounded. Never use actual URLs, request IDs, user IDs, statement references, filenames, paths, or exception messages as labels.

Do not expose passwords, API keys, bearer values, authorization headers, identity claims, raw user identities, database connection strings, SQL, statement contents, provider URLs or payloads, or uncontrolled exception text in logs, traces, metrics, or error responses.
