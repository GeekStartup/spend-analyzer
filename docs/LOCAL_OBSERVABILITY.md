# Local Observability Runbook

## Purpose

Spend Analyzer provides an optional local profile for Prometheus metrics, PostgreSQL metrics, and Tempo traces. Structured JSON logs are written to application stdout.

## Architecture

```text
FastAPI /metrics -------------------+
                                     +--> Prometheus --> Grafana
PostgreSQL exporter /metrics -------+

FastAPI traces --> OpenTelemetry Collector --> Tempo --> Grafana
FastAPI structured logs ------------------------------> stdout
```

## Configuration

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Relevant settings:

```dotenv
LOG_LEVEL=INFO
LOG_FORMAT=json
METRICS_ENABLED=true
METRICS_PATH=/metrics
TRACING_ENABLED=false
OTEL_SERVICE_NAME=spend-analyzer-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SAMPLE_RATIO=1.0
```

Use `LOG_LEVEL=DEBUG` only when selected internal checkpoints are needed. The application does not log every function entry and exit.

Tracing is disabled by default. Enable it only when the Collector is available.

## Validate and start

```powershell
docker compose config --quiet
docker compose --profile observability config --quiet
docker compose -f docker-compose.test.yml config --quiet

docker compose --profile observability up --build -d
docker compose --profile observability ps -a
```

Expected long-running services:

```text
app
db
identity-provider
otel-collector
prometheus
grafana
tempo
postgres-exporter
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
| PostgreSQL exporter | `http://localhost:9187/metrics` |

## Inspect logs

```powershell
docker compose logs --follow --no-color app
```

One `http.request` outcome log is emitted for each non-metrics request.

Its `url` field is a safe relative request target:

- dynamic path values are replaced by the resolved route template;
- query parameter names may be retained;
- every query parameter value is replaced with `[REDACTED]`;
- scheme, host, port, fragment, headers, and body are excluded.

Example:

```json
{
  "event": "http.request",
  "method": "GET",
  "url": "/items/{item_id}?source=%5BREDACTED%5D",
  "status_code": 200,
  "duration_ms": 12.4,
  "request_id": "request-123",
  "trace_id": "...",
  "span_id": "..."
}
```

Logging policy:

| Level | Meaning |
|---|---|
| DEBUG | Selected internal diagnostic checkpoint |
| INFO | Lifecycle, successful business outcome, and `2xx` request outcome |
| ERROR | Controlled failure diagnostic and `4xx` or `5xx` request outcome |

Useful searches:

```powershell
docker compose logs --no-color app |
    Select-String '"event":"Database health check failed"'

docker compose logs --no-color app |
    Select-String '"event":"Identity provider operation failed"'

docker compose logs --no-color app |
    Select-String '"statement_reference":"statement-123"'
```

## Problem Details and request correlation

All application and framework `4xx` and `5xx` responses use `application/problem+json`.

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

The response also contains:

```text
X-Request-ID: request-123
```

Debug workflow:

1. copy `request_id` from the response body or header;
2. search application logs by request ID;
3. inspect the controlled diagnostic event and final `http.request` event;
4. when tracing is enabled, use `trace_id` from the log to open the request trace in Tempo.

```powershell
docker compose logs --no-color app |
    Select-String '"request_id":"<request-id>"'
```

A failed request can produce one controlled diagnostic log plus one HTTP outcome log. This is intentional and is not duplicate request start/end logging.

## Inspect application metrics

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

Useful PromQL:

```promql
rate(http_requests_total[5m])
histogram_quantile(
  0.95,
  sum by (le, handler) (rate(http_request_duration_seconds_bucket[5m]))
)
statement_ingestion_failures_total
auth_failures_total
file_storage_failures_total
app_dependency_health_status
```

Dependency gauge examples:

```text
app_dependency_health_status{dependency="database"} 1.0
app_dependency_health_status{dependency="identity_provider"} 1.0
```

HTTP metrics use bounded route templates. Actual paths, query values, request IDs, user IDs, and exception messages never appear as metric labels.

## Inspect PostgreSQL metrics

```powershell
$postgresMetrics = (
    Invoke-WebRequest -UseBasicParsing http://localhost:9187/metrics
).Content

$postgresMetrics | Select-String "pg_up"
$postgresMetrics | Select-String "activity|locks|connections"
```

Expected connectivity sample:

```text
pg_up 1
```

The PostgreSQL exporter remains the database-observability path until real repository/query flows justify dedicated instrumentation. Do not record SQL, bind values, credentials, or raw driver messages.

## Inspect traces

Enable tracing:

```dotenv
TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

Recreate the application container:

```powershell
docker compose --profile observability up -d --force-recreate app
```

Generate health, authentication, and ingestion requests. In Grafana **Explore**, select Tempo and search for service `spend-analyzer-api`.

Issue #78 uses automatic infrastructure tracing:

- incoming FastAPI requests produce server spans;
- supported outbound `requests` calls produce client spans;
- configured identity-provider issuer and JWKS endpoints are excluded from generic outbound tracing;
- application routes and services do not create manual business or dependency spans;
- custom business spans are deferred to separate work.

The tracing pipeline sanitizes completed spans before batching and export. Raw path values, query values, credentials, exception messages, stack traces, and status descriptions are not exported.

`/metrics` scrapes are excluded from request logs, HTTP metrics, and traces.

## Failure workflows

### Database health

- copy the request ID from the 503 response;
- search for `Database health check failed`;
- inspect `failure_category`, `cause_type`, and the database dependency gauge;
- open the automatic `GET /health/db` server trace using the correlated `trace_id`.

### Identity provider

- search for `Identity provider operation failed`;
- inspect `failure_category`, `cause_type`, and `timeout_seconds` when present;
- inspect the identity-provider dependency gauge;
- correlate through the request ID and automatic incoming request trace.

Identity-provider endpoints are excluded from generic outbound tracing to prevent provider URLs, payload-derived values, or uncontrolled exception details from entering spans. Identity-provider outages return 503 and do not increment invalid-credential metrics.

### Statement ingestion

| Failure | Log message | Status |
|---|---|---:|
| Invalid PDF | `Statement ingestion rejected an invalid PDF` | 400 |
| Upload too large | `Statement ingestion rejected an oversized upload` | 413 |
| Storage unavailable | `Statement ingestion failed because file storage is unavailable` | 503 |
| Internal storage error | `Statement ingestion failed because of an unexpected storage error` | 500 |

Use request ID, trace ID, and generated statement reference to correlate ingestion signals. Original filenames, raw user IDs, request path values, file content, and raw exception messages are intentionally absent.

## Safe telemetry rules

Allowed when operationally useful:

- controlled event messages;
- request, trace, and span identifiers;
- safe route templates and redacted query values;
- HTTP method, status, and duration;
- generated statement reference;
- normalized content type;
- counts, sizes, configured limits, and bounded categories;
- exception class name.

Never record:

- passwords, secrets, tokens, authorization headers, or claims;
- raw user IDs, usernames, or email addresses;
- concrete path values or query values;
- database URLs, SQL, or bind values;
- identity-provider URLs or payloads;
- raw exception messages or stack traces;
- original sensitive filenames;
- statement content or financial identifiers.

## Future features

For each meaningful operation:

1. write a clear structured log with a small set of safe fields;
2. add a metric only when aggregation is operationally useful;
3. add a custom span only around a meaningful business or dependency boundary;
4. preserve request and trace correlation;
5. add behavioural and sensitive-data exclusion tests.

Do not add another logging facade, instrument every helper, or log every function entry and exit.

Centralized log storage remains out of scope. Add Loki, OpenSearch, or ELK only when retention, multi-instance search, or incident volume justifies the operational cost.
