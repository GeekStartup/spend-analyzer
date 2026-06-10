# Local Observability Runbook

## Purpose

Spend Analyzer provides an optional local profile for Prometheus metrics, PostgreSQL metrics, and Tempo traces. Structured JSON logs always go to application stdout.

## Architecture

```text
FastAPI /metrics -------------------+
                                     +--> Prometheus --> Grafana
PostgreSQL exporter /metrics -------+

FastAPI traces --> Collector --> Tempo --> Grafana
FastAPI structured logs -----------> container stdout
```

## Configuration

```powershell
Copy-Item .env.example .env
```

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

Use `LOG_LEVEL=DEBUG` temporarily for selected checkpoints such as JWKS cache misses and upload byte counts. DEBUG does not log every function entry/exit.

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

One `http.request` log is emitted per non-metrics request. Its `url` is the actual relative path plus optional query string, with no scheme or host.

| Level | Meaning |
|---|---|
| DEBUG | Selected internal diagnostic checkpoint |
| INFO | Lifecycle, business outcome, expected client rejection |
| WARNING | Handled dependency/infrastructure failure |
| ERROR | Unexpected application/internal failure |

Search examples:

```powershell
docker compose logs --no-color app |
    Select-String '"event":"Database health check failed"'

docker compose logs --no-color app |
    Select-String '"event":"Identity provider key retrieval failed"'

docker compose logs --no-color app |
    Select-String '"statement_reference":"statement-123"'
```

## Problem Details and request correlation

All `4xx` and `5xx` responses use `application/problem+json`.

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

The response header also contains:

```text
X-Request-ID: request-123
```

Clients should show the request ID on error screens so users can provide it to support.

Debug workflow:

1. copy `request_id` from the body or header;
2. search logs by request ID;
3. inspect the business/dependency diagnostic and `http.request` outcome;
4. use `trace_id` from the log to open the trace in Tempo.

```powershell
docker compose logs --no-color app |
    Select-String '"request_id":"<request-id>"'
```

A failed request may produce one business/dependency diagnostic plus one HTTP outcome log. This is intentional; it is not duplicate request start/end logging.

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

Actual request URLs never appear as metric labels.

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

The exporter remains the database-observability path until real repository/query flows exist. Future database operations should add safe diagnostics at meaningful repository/service boundaries, without SQL, bind values, or raw driver messages.

## Inspect traces

Enable tracing:

```dotenv
TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

```powershell
docker compose --profile observability up -d --force-recreate app
```

Generate health and authenticated requests, then open Grafana **Explore**, select Tempo, and search service `spend-analyzer-api`.

Relevant child spans:

```text
database.health_check
identity_provider.jwks_fetch
statement.ingestion
```

`/metrics` scrapes are excluded from request logs, HTTP metrics, and traces.

## Failure workflows

### Database health

- copy the request ID from the 503 response;
- search for `Database health check failed` or `Database health check returned an unhealthy result`;
- inspect duration and exception class when present;
- inspect the database dependency gauge and `database.health_check` span.

### Identity provider

- search for `Identity provider key retrieval failed` or `Identity provider returned an invalid signing-key response`;
- inspect exception class and configured timeout where present;
- inspect the identity-provider dependency gauge and `identity_provider.jwks_fetch` span.

Identity-provider outages return 503 and are not counted as invalid credentials.

### Statement ingestion

| Failure | Log message | Status |
|---|---|---:|
| Invalid PDF | `Statement ingestion rejected an invalid PDF` | 400 |
| Upload too large | `Statement ingestion rejected an oversized upload` | 413 |
| Storage unavailable | `Statement ingestion failed because file storage is unavailable` | 503 |
| Internal storage error | `Statement ingestion failed because of an unexpected storage error` | 500 |

Use request ID, trace ID, and generated statement reference to correlate signals. Original filename, raw user ID, path, content, and raw exception message are intentionally absent.

## Safe telemetry rules

Allowed when useful:

- controlled messages;
- request/trace/span IDs;
- relative URL under the API URL contract;
- method, status, duration;
- generated statement reference;
- normalized content type;
- counts, sizes, configured limits;
- bounded metric/span categories;
- exception class.

Never record:

- passwords, secrets, tokens, authorization headers, or claims;
- raw user IDs, usernames, or emails;
- database URLs, SQL, or bind values;
- identity-provider URLs or payloads;
- raw exception messages or stack traces;
- original sensitive filenames;
- statement content or financial identifiers.

## Future features

For each meaningful operation:

1. write a clear normal logger message with a few safe fields;
2. add a metric only when aggregation is useful;
3. add a span only around a meaningful business/dependency boundary;
4. preserve correlation;
5. add behavioural and data-exclusion tests.

Do not add a logging facade, instrument every helper, or log every function entry and exit.

Centralized log storage remains out of scope. Add Loki/OpenSearch/ELK only when retention, multi-instance search, or incident volume justifies it.
