# Local Observability Runbook

## Start the stack

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose --profile observability config --quiet
docker compose -f docker-compose.test.yml config --quiet
docker compose --profile observability up --build -d
```

Tracing is disabled by default. Enable it only when the Collector is running:

```dotenv
TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

Stop without deleting volumes:

```powershell
docker compose --profile observability down
```

## Endpoints

| Service | URL |
|---|---|
| Application health | `http://localhost:8000/health` |
| Database health | `http://localhost:8000/health/db` |
| Application metrics | `http://localhost:8000/metrics` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` |
| Tempo readiness | `http://localhost:3200/ready` |

## Logs and request correlation

```powershell
docker compose logs --follow --no-color app
```

Each non-metrics request emits one `http.request` outcome log with method, status, duration, request ID, and sanitized relative URL.

Query-parameter names remain visible, while all values are replaced with `[REDACTED]`. For example:

```text
/statements?institution=%5BREDACTED%5D&page=%5BREDACTED%5D
```

Application `4xx` and `5xx` responses use `application/problem+json`, include the same request ID in the response body and `X-Request-ID` header, and return the sanitized relative URL.

Debug workflow:

1. Copy `request_id` from the response.
2. Search application logs for the same request ID.
3. Inspect the centralized diagnostic and final `http.request` outcome.
4. Use `trace_id` to inspect Tempo when tracing is enabled.
5. Check bounded dependency and failure metrics.

```powershell
docker compose logs --no-color app |
    Select-String '"request_id":"<request-id>"'
```

## Metrics

```powershell
$metrics = (
    Invoke-WebRequest -UseBasicParsing http://localhost:8000/metrics
).Content

$metrics | Select-String "http_requests_total"
$metrics | Select-String "statement_ingestion"
$metrics | Select-String "auth_failures_total"
$metrics | Select-String "file_storage_failures_total"
$metrics | Select-String "app_dependency_health_status"
```

Actual request URLs are never metric labels.

## Traces

Current tracing is infrastructure-level:

- incoming FastAPI request spans;
- automatic outbound `requests` spans, except configured identity-provider issuer and JWKS endpoints.

There are no custom database-health, JWKS, or statement-ingestion spans in Issue #78.

Before export, query values, exception messages, stack traces, and span status descriptions are removed. Only controlled attributes such as exception class may remain.

`/metrics` is excluded from request logs, HTTP metrics, and traces.

## Failure workflows

### Database health

- Search for `Database health check failed`.
- Check `app_dependency_health_status{dependency="database"}`.
- Inspect the containing FastAPI request trace.

### Identity provider

- Search for `Identity provider operation failed`.
- Check `app_dependency_health_status{dependency="identity_provider"}`.
- Identity-provider endpoints are excluded from outbound traces.
- Provider outages and malformed JWKS responses return 503 and do not count as invalid credentials.

### Statement ingestion

| Failure | Log message | Status |
|---|---|---:|
| Invalid PDF | `Statement ingestion rejected an invalid PDF` | 400 |
| Upload too large | `Statement ingestion rejected an oversized upload` | 413 |
| Storage unavailable | `Statement ingestion failed because file storage is unavailable` | 503 |
| Internal storage error | `Statement ingestion failed because of an unexpected storage error` | 500 |

## Safe telemetry rules

Allowed fields include controlled event names, correlation IDs, sanitized relative URLs, method, status, duration, generated references, counts, sizes, bounded categories, and exception class names.

Do not record credentials, identity data, query values, database connection details, SQL, provider endpoints or payloads, uncontrolled exception text, statement contents, or financial identifiers.
