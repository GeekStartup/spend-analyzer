# Local Observability Runbook

## Purpose

Spend Analyzer provides an optional local observability profile for inspecting application metrics, PostgreSQL metrics, and distributed traces.

The normal application stack does not depend on this profile. Structured JSON logs continue to be written to container stdout.

## Architecture

```text
FastAPI /metrics -------------------+
                                     +--> Prometheus --> Grafana
PostgreSQL exporter /metrics -------+

FastAPI OTLP traces
        |
        v
OpenTelemetry Collector --> Tempo --> Grafana

FastAPI structured JSON logs --> container stdout
```

Responsibilities:

| Component | Responsibility |
|---|---|
| FastAPI | Emits structured logs, exposes application metrics, and creates traces |
| PostgreSQL exporter | Exposes PostgreSQL activity, connection, lock, and database metrics |
| Prometheus | Scrapes and stores application and PostgreSQL metrics |
| OpenTelemetry Collector | Receives, batches, and forwards OTLP traces |
| Tempo | Stores local traces |
| Grafana | Provides metric and trace exploration |

## Configuration

Create the local environment file before using Docker Compose:

```powershell
Copy-Item .env.example .env
```

Relevant application settings:

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

Tracing is disabled by default so the application can run without the optional Collector. Set `TRACING_ENABLED=true` only when the observability profile or another configured OTLP collector is available.

`METRICS_PATH` must not conflict with an existing FastAPI route. The local Prometheus configuration currently scrapes `/metrics`; changing `METRICS_PATH` also requires changing `metrics_path` in `infra/observability/prometheus.yml`.

## Validate configuration

Validate both normal and profile-expanded Compose configuration:

```powershell
docker compose config --quiet
docker compose --profile observability config --quiet
docker compose -f docker-compose.test.yml config --quiet
```

These checks run in local CI and GitHub Actions.

## Start and stop

Start the complete local stack:

```powershell
docker compose --profile observability up --build -d
```

Inspect service state:

```powershell
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

Flyway is a one-shot migration container and should exit with code `0`.

Stop the stack while preserving PostgreSQL and observability data:

```powershell
docker compose --profile observability down
```

Do not add `-v` unless deleting PostgreSQL, Prometheus, Tempo, and Grafana volumes is intentional.

## Local endpoints

| Service | URL |
|---|---|
| Application health | `http://localhost:8000/health` |
| Database health | `http://localhost:8000/health/db` |
| Application metrics | `http://localhost:8000/metrics` |
| Prometheus | `http://localhost:9090` |
| Prometheus targets | `http://localhost:9090/targets` |
| Grafana | `http://localhost:3000` |
| Tempo readiness | `http://localhost:3200/ready` |
| PostgreSQL exporter | `http://localhost:9187/metrics` |

Observability ports bind to `127.0.0.1` and are intended for local use only.

## Inspect metrics

Verify the application endpoint:

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

Call the database health endpoint, then verify the dependency gauge:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health/db

(
    Invoke-WebRequest -UseBasicParsing http://localhost:8000/metrics
).Content | Select-String "app_dependency_health_status"
```

Expected healthy sample:

```text
app_dependency_health_status{dependency="database"} 1.0
```

In Prometheus, inspect `http://localhost:9090/targets`. Both jobs should be `UP`:

```text
spend-analyzer-api
spend-analyzer-postgresql
```

Useful PromQL examples:

```promql
up
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

## Inspect PostgreSQL metrics

Verify exporter connectivity:

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

The exporter provides local visibility into connection counts, activity, locks, transactions, database statistics, table statistics, and selected long-running transaction indicators.

This is the current database-observability path. Future repository/database work should add safe database spans and slow-query instrumentation only after query execution patterns and sanitization rules are mature. SQL text, bind values, credentials, and financial data must not be recorded.

## Inspect traces

Set the following in the local `.env`:

```dotenv
TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

Recreate the application container:

```powershell
docker compose --profile observability up -d --force-recreate app
```

Generate traces:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health/db
```

In Grafana:

1. Open **Explore**.
2. Select the **Tempo** data source.
3. Search for service `spend-analyzer-api`.
4. Open a `GET /health/db` trace.
5. Confirm the child span `database.health_check`.

Metrics scrapes are excluded from request logs, HTTP metrics, and traces.

## Debug using request ID

Every HTTP response includes `X-Request-ID`. A caller may also supply this header; the application preserves it.

Capture the value from the failed response:

```powershell
try {
    Invoke-WebRequest -UseBasicParsing http://localhost:8000/example
}
catch {
    $_.Exception.Response.Headers["X-Request-ID"]
}
```

Search container logs for the same value:

```powershell
docker compose logs --no-color app |
    Select-String '"request_id":"<request-id>"'
```

When tracing is enabled, the same request-summary or business-event log also contains `trace_id` and `span_id`. Use `trace_id` to locate the corresponding trace in Tempo.

## Safe telemetry rules

### Logs

Logs may include:

- bounded event names;
- request ID;
- route template;
- HTTP method and status;
- duration;
- generated statement reference;
- normalized content type;
- file size;
- bounded outcome and failure categories;
- exception class name.

Logs must not include:

- passwords, API keys, tokens, or authorization headers;
- database URLs or credentials;
- raw exception messages or stack traces;
- original filenames when they may be sensitive;
- statement contents, extracted text, account numbers, or card numbers;
- user-provided financial descriptions.

The request middleware emits one outcome-summary event rather than duplicate request-start and request-completion events.

### Metrics

Metric labels must be bounded. Never use:

- request ID, trace ID, or span ID;
- user ID;
- statement reference;
- filename;
- raw route path;
- exception message;
- arbitrary institution/account text.

### Traces

Trace attributes and exception events must use safe, bounded values. The application records exception class names without raw exception messages or stack traces. Do not attach SQL text, bind values, tokens, filenames, statement contents, account identifiers, or user-provided financial data.

## Future feature convention

A future backend feature should use the existing foundation instead of creating new middleware or telemetry infrastructure.

For each meaningful operation:

1. Add a safe structured business event for important outcomes.
2. Add a bounded counter, gauge, or histogram when aggregation is useful.
3. Add a manual span around a meaningful business or dependency boundary.
4. Preserve request and trace context.
5. Record bounded failure categories.
6. Add tests for telemetry side effects and sensitive-data exclusion.
7. Update operational debugging notes where applicable.

## Centralized log search decision

OpenSearch, Elasticsearch/ELK, and Loki are intentionally not deployed in this issue.

Structured JSON logs to stdout are sufficient for the current MVP, while Prometheus and Tempo provide local metric and trace inspection. A centralized log backend should be added only when log volume, retention, multi-instance search, or incident-investigation needs justify its operational cost.

OpenTelemetry keeps future telemetry routing backend-neutral.
