# Low-Level Design (LLD) — Spend Analyzer

## 1. Purpose

This document describes the low-level backend design for Spend Analyzer.

It covers modules, configuration, API contracts, validation, error handling, service boundaries, storage, database schema, security, and quality gates. High-level architecture belongs in [`HLD.md`](HLD.md). Detailed observability decisions belong in [`OBSERVABILITY_LLD.md`](OBSERVABILITY_LLD.md). Operational observability commands belong in [`LOCAL_OBSERVABILITY.md`](LOCAL_OBSERVABILITY.md). Parser-specific design belongs in [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

---

## 2. Design Status

### 2.1 Implemented

- FastAPI backend application
- Environment-driven configuration with Pydantic Settings
- PostgreSQL connectivity
- Flyway database migrations
- Local Keycloak/OIDC setup
- JWT validation and authenticated-user context
- `GET /health`
- `GET /health/db`
- `GET /me`
- `POST /ingest`
- Secure local PDF storage
- Typed application exceptions
- Central RFC 9457-compatible Problem Details handling
- Request-ID propagation and structured HTTP outcome logging
- Prometheus-compatible HTTP and business metrics
- Automatic FastAPI and supported outbound HTTP tracing
- Pre-export span sanitization
- Docker Compose local/test runtime
- Strict CI quality gates

### 2.2 Planned

- Persist uploaded statement metadata from the ingestion API
- PDF text/table extraction
- Statement format detection
- Generic transaction parser
- Broad bank/account parsers
- AI parsing fallback
- Transaction persistence
- Rule-based and AI-assisted categorization
- Analytics APIs
- AI insight APIs
- Natural-language query layer
- RAG and semantic retrieval
- Controlled finance agent
- Frontend
- Cloud deployment

---

## 3. Repository Structure

```text
app/
├── main.py
├── config.py
├── errors.py
├── http.py
├── problem_details.py
├── api/
│   ├── health_routes.py
│   ├── ingest_routes.py
│   └── me_routes.py
├── auth/
│   ├── dependencies.py
│   └── jwt_validator.py
├── db/
│   └── connection.py
├── observability/
│   ├── context.py
│   ├── logging.py
│   ├── metrics.py
│   ├── middleware.py
│   └── tracing.py
├── schemas/
│   ├── auth_schema.py
│   ├── health_schema.py
│   └── ingest_schema.py
└── services/
    ├── file_storage_service.py
    └── health_service.py
```

Future additions:

```text
app/repositories/
app/parsing/
app/ai/
app/rag/
app/agents/
```

### 3.1 Module responsibilities

| Module | Responsibility |
|---|---|
| `main.py` | Application construction, lifecycle logging, middleware/handler registration, metrics and tracing configuration |
| `config.py` | Typed environment configuration |
| `errors.py` | Controlled application exception hierarchy and safe context |
| `http.py` | Safe request-target and absolute-URL sanitization |
| `problem_details.py` | Exception-to-Problem mapping, safe diagnostics, response creation |
| `api/*` | HTTP routes and application-boundary orchestration |
| `auth/dependencies.py` | Bearer-token dependency and auth-failure classification |
| `auth/jwt_validator.py` | JWKS retrieval, key validation, JWT validation |
| `db/connection.py` | Database connection/check helper |
| `observability/context.py` | Request correlation context |
| `observability/logging.py` | Structured JSON logging and unsafe exception-input removal |
| `observability/middleware.py` | Request ID, timing, containment, response header, HTTP outcome log |
| `observability/metrics.py` | One shared Prometheus metric registry |
| `observability/tracing.py` | Automatic HTTP instrumentation and span sanitization |
| `services/file_storage_service.py` | Upload validation and safe local persistence |
| `services/health_service.py` | Health response construction |

Routes, services, and repositories must not create alternative middleware, tracer providers, metric registries, or error response formats.

---

## 4. Configuration Design

Configuration is loaded through `app/config.py` using Pydantic Settings. Modules import the typed `settings` object rather than reading environment variables directly.

### 4.1 Application

```text
APP_NAME
APP_ENV
APP_VERSION
APP_PORT
```

### 4.2 Database

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

The application derives the PostgreSQL connection URL internally. It must not be logged.

### 4.3 Identity provider

```text
KEYCLOAK_ADMIN
KEYCLOAK_ADMIN_PASSWORD
OIDC_ISSUER_URL
OIDC_JWKS_URL
OIDC_AUDIENCE
OIDC_CLIENT_ID
```

### 4.4 Storage

```text
UPLOAD_DIR
MAX_UPLOAD_SIZE_BYTES
STORAGE_TYPE
```

Current storage type:

```text
local
```

Future storage type:

```text
s3
```

### 4.5 Logging, metrics, and tracing

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

Rules:

- tracing is disabled by default;
- the application remains functional without the optional Collector;
- `METRICS_PATH` must not conflict with an application route;
- metric scrapes are excluded from request logs, HTTP metrics, and traces;
- application code does not import tracing APIs to manage normal HTTP spans.

### 4.6 AI

```text
OPENAI_API_KEY
OPENAI_MODEL
```

AI is enabled only when the API key is non-blank.

---

## 5. Application Wiring

`create_app()` performs the following high-level steps:

1. configure structured logging;
2. create the FastAPI application;
3. add request-context middleware;
4. register central Problem Details handlers;
5. configure automatic tracing;
6. include application routers;
7. expose HTTP metrics after checking route availability.

Lifecycle behavior:

- one structured `Application started` event;
- one structured `Application stopped` event;
- no custom lifecycle metric or span.

This ordering ensures common request behavior is installed once and keeps business code independent of telemetry plumbing.

---

## 6. Authentication and Authorization

The backend is an OAuth2/OIDC resource server.

The identity provider owns:

- user registration;
- password storage;
- password reset;
- login UI;
- token issuance.

The backend owns:

- bearer-token extraction;
- JWKS retrieval and caching;
- signing-key validation;
- signature, issuer, audience, and expiry validation;
- authenticated-user construction;
- authorization based on token-derived identity.

### 6.1 User identifier rule

```text
user_id = validated_token["sub"]
```

The backend must never accept a request-body or query-string `user_id` for ownership decisions.

### 6.2 Failure taxonomy

| Failure | Typed exception | Status | Metric category |
|---|---|---:|---|
| Missing bearer token | `AuthenticationRequiredError` | 401 | `missing_credentials` |
| Invalid/expired/malformed token | `InvalidCredentialsError` | 401 | `credentials_invalid` |
| JWKS request failed | `IdentityProviderUnavailableError` | 503 | dependency health `identity_provider=0` |
| JWKS response unusable | `IdentityProviderUnavailableError` | 503 | dependency health `identity_provider=0` |

Identity-provider failure is not an authentication failure. It must not increment `auth_failures_total`.

### 6.3 JWKS validation

A JWKS response is usable only when:

- the response is an object;
- `keys` is a non-empty list;
- entries are objects;
- at least one supported RSA signing key has:
  - non-empty `kid`;
  - `kty=RSA`;
  - signing use;
  - supported algorithm;
  - modulus `n`;
  - exponent `e`.

Safe diagnostic context may include dependency name, operation, bounded category, exception class, and configured timeout. It must not include token data, key IDs, URLs, provider payloads, or raw exception messages.

---

## 7. API Layer

| Module | Current responsibility |
|---|---|
| `health_routes.py` | Application and database health APIs |
| `me_routes.py` | Authenticated-user inspection |
| `ingest_routes.py` | Authenticated PDF upload |

Future route modules:

| Module | Responsibility |
|---|---|
| `transaction_routes.py` | Transaction listing and filtering |
| `summary_routes.py` | Monthly summary APIs |
| `comparison_routes.py` | Month-on-month comparisons |
| `insight_routes.py` | AI-generated insights |
| `query_routes.py` | Natural-language queries |

API routes should:

- validate/normalize transport input;
- invoke application services;
- record bounded business metrics when useful;
- raise typed application exceptions;
- return typed response schemas.

API routes should not:

- construct ad hoc error JSON;
- log the same failure that the central handler logs;
- calculate request duration;
- create or mutate OpenTelemetry spans;
- execute SQL directly.

---

## 8. Current API Endpoints

### 8.1 `GET /health`

Returns application health and service metadata.

```json
{
  "status": "OK",
  "service": {
    "name": "Spend Analyzer",
    "environment": "local",
    "version": "0.1.0"
  },
  "checks": {
    "application": {
      "status": "OK",
      "message": "Application is running",
      "error": null
    }
  }
}
```

Successful calls use baseline HTTP telemetry only.

### 8.2 `GET /health/db`

Returns application metadata and database health.

Successful response:

```json
{
  "status": "OK",
  "service": {
    "name": "Spend Analyzer",
    "environment": "local",
    "version": "0.1.0"
  },
  "checks": {
    "database": {
      "status": "OK",
      "message": "Database is reachable",
      "error": null
    }
  }
}
```

Behavior:

- successful check sets `app_dependency_health_status{dependency="database"}` to `1`;
- failed/unhealthy check sets it to `0`;
- database-driver failures raise `DatabaseUnavailableError`;
- failures return a centralized `503` Problem Details response;
- the request uses the automatic incoming server span;
- no manual database-health child span is created.

### 8.3 `GET /me`

Requires a valid bearer token.

```json
{
  "user_id": "oidc-sub",
  "username": "test.user",
  "email": "test.user@example.com"
}
```

Successful calls use baseline HTTP telemetry only. Identity fields are returned to the authenticated client but are not automatically added to logs, metrics, or traces.

### 8.4 `POST /ingest`

Requires a valid bearer token and `multipart/form-data`.

Request fields:

| Field | Required | Description |
|---|---:|---|
| `file` | Yes | PDF statement |
| `institution` | No | User-provided institution hint |
| `account_type` | No | User-provided account-type hint |
| `account_name` | No | User-friendly account/card name |
| `statement_format` | No | User-provided format hint |

Success response:

```json
{
  "statement_reference": "generated-uuid",
  "original_file_name": "statement.pdf",
  "stored_file_name": "generated-file-name.pdf",
  "content_type": "application/pdf",
  "file_size_bytes": 12345,
  "status": "UPLOADED",
  "institution": "hdfc",
  "account_type": "credit_card",
  "account_name": "HDFC Swiggy",
  "statement_format": "hdfc_credit_card"
}
```

Current limitation:

- the endpoint stores the file and returns upload metadata;
- statement metadata persistence and parsing are follow-up work.

---

## 9. Typed Error Model

### 9.1 Exception hierarchy

```text
ApplicationError
├── AuthenticationRequiredError
├── InvalidCredentialsError
├── DatabaseUnavailableError
├── IdentityProviderUnavailableError
└── FileStorageError
    ├── InvalidPdfError
    ├── FileStorageUnavailableError
    └── UploadTooLargeError
```

All Python exceptions are unchecked; callers are not required by the language to declare or catch them.

`ApplicationError` carries:

- a private internal message for exception chaining/debugging;
- a context dictionary that can be enriched at application boundaries.

The central handler applies an allowlist before any context is logged.

### 9.2 Separation of responsibilities

```text
Route/service:
    raise typed ApplicationError

Central handler:
    choose status/problem type/title/detail
    emit one controlled diagnostic log
    create Problem Details response

Middleware:
    add request ID
    add response header
    measure duration
    emit final http.request outcome
```

This is equivalent in responsibility to a Spring `RuntimeException` hierarchy plus `@RestControllerAdvice` and a `OncePerRequestFilter`.

---

## 10. Problem Details Contract

All application and framework `4xx`/`5xx` responses use:

```text
Content-Type: application/problem+json
```

Required response members:

```text
type
title
status
detail
instance
request_id
url
```

Example:

```json
{
  "type": "urn:spend-analyzer:problem:invalid-pdf",
  "title": "Invalid PDF",
  "status": 400,
  "detail": "The uploaded file is not a valid PDF.",
  "instance": "urn:spend-analyzer:request:request-123",
  "request_id": "request-123",
  "url": "/ingest"
}
```

The response header contains the same request ID:

```text
X-Request-ID: request-123
```

### 10.1 Stable mappings

| Exception/status | HTTP status | Problem type suffix |
|---|---:|---|
| `AuthenticationRequiredError` | 401 | `authentication-required` |
| `InvalidCredentialsError` | 401 | `invalid-credentials` |
| `InvalidPdfError` | 400 | `invalid-pdf` |
| `UploadTooLargeError` | 413 | `upload-too-large` |
| `DatabaseUnavailableError` | 503 | `database-unavailable` |
| `IdentityProviderUnavailableError` | 503 | `identity-provider-unavailable` |
| `FileStorageUnavailableError` | 503 | `file-storage-unavailable` |
| `FileStorageError` | 500 | `internal-server-error` |
| Unknown framework HTTP status | original status | `http-error` |
| Unexpected exception | 500 | `internal-server-error` |

### 10.2 Safety rules

Handlers must not copy:

- raw `HTTPException.detail`;
- raw Pydantic input;
- raw validation messages;
- exception messages;
- tracebacks;
- stack-frame metadata;
- arbitrary exception context.

Validation errors expose only:

```text
code
location
controlled message
```

Protocol headers such as `WWW-Authenticate` and `Allow` are preserved.

Problem extension fields cannot overwrite standard members.

---

## 11. Request Context and HTTP Outcome Logging

### 11.1 Request ID

The middleware accepts a caller-supplied `X-Request-ID` only when it matches the bounded allowed pattern. Otherwise, it generates a UUID.

The request ID is:

- bound to structured logging context;
- stored on `request.state`;
- returned in every response header;
- included in every Problem Details response;
- cleared after the request completes.

### 11.2 Safe URL

The safe request target contains:

- route template rather than concrete path values;
- at most a bounded number of query parameter names;
- redacted query values;
- no host, scheme, port, fragment, headers, or body.

Examples:

```text
/items/{item_id}
/items/{item_id}?source=%5BREDACTED%5D
/<unmatched>?source=%5BREDACTED%5D
```

The URL is event-local data. It is not bound to every application log.

### 11.3 Outcome log

Exactly one non-metrics HTTP outcome event is emitted:

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

Policy:

- successful outcomes below `400` are INFO;
- `4xx` and `5xx` outcomes are ERROR;
- request duration is calculated automatically;
- separate request-start and request-completion logs are not emitted;
- `/metrics` is excluded.

A failed request may produce:

1. one central diagnostic event explaining the controlled failure;
2. one `http.request` event describing status and duration.

These events serve different purposes and are not duplicate start/end logs.

---

## 12. Structured Logging Safety

The logging pipeline emits JSON and automatically adds active trace/span identifiers.

A global processor removes:

```text
exc_info
stack_info
```

before rendering.

Unhandled exceptions log only bounded metadata such as:

- exception class name;
- exception module;
- status;
- stable problem type;
- request/trace correlation identifiers.

They do not log raw messages, traceback text, file paths, function names, line numbers, or traceback-derived frame summaries.

Application code uses the logger directly:

```python
logger.info("Statement ingestion succeeded", file_size_bytes=file_size_bytes)
logger.debug("Statement upload content read", file_size_bytes=file_size_bytes)
```

Do not log every function entry and exit.

---

## 13. Metrics Design

HTTP instrumentation supplies bounded request count, grouped status, sizes, and duration using route templates.

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

Allowed labels are fixed, bounded categories.

Never use as metric labels:

- request, trace, or span IDs;
- user IDs;
- statement references;
- filenames;
- request targets;
- exception messages;
- arbitrary institution/account values.

---

## 14. Tracing Design

Tracing is configured once in `main.py`.

Automatic instrumentation:

- `FastAPIInstrumentor` for incoming HTTP requests;
- `RequestsInstrumentor` for supported outbound `requests` calls.

Application routes and services do not create manual spans for the current flows.

### 14.1 Server span attributes

The server request hook writes safe attributes:

```text
http.route
http.target
http.url
url.full
url.path
url.query
```

Concrete dynamic paths are replaced with route templates and query values are redacted.

### 14.2 Client span attributes

Outbound URLs remove:

- URL userinfo credentials;
- concrete path values;
- query values;
- fragments.

### 14.3 Pre-export sanitization

Every completed span passes through a sanitizing processor before batching/export.

The processor:

- sanitizes `http.url` and `url.full`;
- replaces `http.target`, `url.path`, and `url.query`;
- removes exception messages and exception stack traces from span events;
- keeps only bounded exception type;
- keeps the span status code but removes uncontrolled status descriptions.

Configured identity-provider issuer and JWKS endpoints are excluded from generic outbound tracing.

---

## 15. Current Upload Implementation

```text
POST /ingest
   |
   v
Validate JWT
   |
   v
Create statement_reference
   |
   v
Record ingestion attempt
   |
   v
Validate filename/content-type metadata
   |
   v
Read file in bounded chunks
   |
   v
Validate content and size
   |
   v
Save under hashed user directory with generated filename
   |
   v
Record success metrics and safe business event
   |
   v
Return StatementUploadResponse
```

### 15.1 File validation

The service rejects:

- missing/blank filenames;
- non-PDF extensions;
- unsupported content types;
- empty files;
- oversized files;
- content without the PDF signature.

### 15.2 Storage path rules

- raw user IDs are not directory names;
- a SHA-256 user storage key is used;
- the original filename is not used as a path component;
- the stored filename is generated from the statement reference and a UUID;
- resolved paths must remain under the configured upload root;
- filesystem `OSError` becomes `FileStorageUnavailableError`;
- blocking writes run in a thread pool.

### 15.3 Failure categories

Statement ingestion:

```text
invalid_pdf
upload_too_large
storage_unavailable
storage_internal_error
```

File storage:

```text
unavailable
internal_error
```

The route records the bounded category, enriches the typed exception with safe stage/operation context, and re-raises. The central handler owns the error log and response.

---

## 16. Current Database Schema

### 16.1 `statements`

Current migration:

```text
infra/db/migration/V2__create_statements_table.sql
```

```sql
CREATE TABLE statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    institution TEXT,
    account_type TEXT,
    account_name TEXT,
    statement_format TEXT,
    original_file_name TEXT NOT NULL,
    stored_file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    parse_confidence NUMERIC(5, 4),
    review_required BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT statements_status_check
        CHECK (status IN ('UPLOADED', 'PARSING', 'PARSED', 'FAILED', 'NEEDS_REVIEW')),

    CONSTRAINT statements_parse_confidence_range_check
        CHECK (parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1),

    CONSTRAINT statements_id_user_id_unique
        UNIQUE (id, user_id)
);
```

Important indexes:

```sql
CREATE INDEX idx_statements_user_uploaded_at
    ON statements (user_id, uploaded_at DESC);

CREATE INDEX idx_statements_user_status
    ON statements (user_id, status);

CREATE INDEX idx_statements_user_review_required
    ON statements (user_id, review_required);
```

### 16.2 `transactions`

Current migration:

```text
infra/db/migration/V3__create_transactions_table.sql
```

```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    statement_id UUID NOT NULL,
    transaction_date DATE NOT NULL,
    description TEXT NOT NULL,
    merchant TEXT,
    category TEXT,
    amount NUMERIC(14, 2) NOT NULL,
    transaction_type TEXT NOT NULL,
    institution TEXT,
    account_type TEXT,
    account_name TEXT,
    source_parser TEXT,
    confidence_score NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT transactions_statement_user_fk
        FOREIGN KEY (statement_id, user_id)
        REFERENCES statements (id, user_id)
        ON DELETE CASCADE,

    CONSTRAINT transactions_type_check
        CHECK (transaction_type IN ('debit', 'credit')),

    CONSTRAINT transactions_amount_non_negative_check
        CHECK (amount >= 0),

    CONSTRAINT transactions_confidence_score_range_check
        CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1)
);
```

Important indexes:

```sql
CREATE INDEX idx_transactions_user_date
    ON transactions (user_id, transaction_date DESC);

CREATE INDEX idx_transactions_user_category
    ON transactions (user_id, category);

CREATE INDEX idx_transactions_user_merchant
    ON transactions (user_id, merchant);

CREATE INDEX idx_transactions_statement_id
    ON transactions (statement_id);

CREATE INDEX idx_transactions_user_source_parser
    ON transactions (user_id, source_parser);
```

Ownership-aware foreign key:

```sql
FOREIGN KEY (statement_id, user_id)
REFERENCES statements (id, user_id)
```

This prevents one user's transaction from referencing another user's statement.

---

## 17. Planned Parsing Pipeline

1. Upload and store PDF.
2. Create statement metadata.
3. Extract text/tables.
4. Detect statement metadata where possible.
5. Run generic parser.
6. Validate result.
7. Run broad bank/account parser if confidence is low.
8. Validate result.
9. Run AI fallback if deterministic confidence remains low.
10. Validate AI candidate transactions.
11. Persist valid transactions or mark `NEEDS_REVIEW`.

Persistence happens only after validation.

### 17.1 Candidate model

```python
class TransactionCandidate(BaseModel):
    transaction_date: date
    description: str
    amount: Decimal
    transaction_type: Literal["debit", "credit"]
    institution: str | None = None
    account_type: Literal["credit_card", "savings_account"] | None = None
    account_name: str | None = None
    product_name: str | None = None
    merchant: str | None = None
    merchant_category: str | None = None
    category: str | None = None
    reference_number: str | None = None
    parser_name: str
    confidence_score: float
```

```python
class ParseResult(BaseModel):
    parser_name: str
    confidence_score: float
    transactions: list[TransactionCandidate]
    warnings: list[str] = []
    errors: list[str] = []
    review_required: bool = False
```

### 17.2 Validation

- required fields;
- dates;
- decimal amounts;
- debit/credit direction;
- duplicate rows;
- statement-period consistency;
- totals/balance reconciliation where available;
- confidence classification.

```text
HIGH    -> persist transactions
MEDIUM  -> persist valid transactions and mark review_required=true
LOW     -> try next parser layer
FAILED  -> try next layer or mark NEEDS_REVIEW/FAILED
```

AI fallback must not bypass validation.

---

## 18. Categorization

Rule-based categorization should be implemented first.

| Keywords | Category |
|---|---|
| swiggy, zomato, restaurant | Food |
| blinkit, instamart, groceries | Groceries |
| uber, ola, fuel, petrol | Travel/Fuel |
| amazon, flipkart | Shopping |
| emi, loan | EMI |
| gst, interest, charges | Fees/Charges |
| bbps payment, cc payment | Credit Card Payment |
| salary | Income |
| electricity, broadband, mobile | Bills |

Fallback:

```text
Other
```

Future:

- AI-assisted fallback;
- merchant normalization;
- user-defined rules.

---

## 19. Repository Layer

Repository modules contain database access only.

Planned repositories:

| Repository | Responsibility |
|---|---|
| `statement_repository.py` | Insert statements, update status, fetch metadata |
| `transaction_repository.py` | Insert/query transactions and aggregate |
| `parser_run_repository.py` | Store parser attempts and bounded debugging metadata |
| `vector_repository.py` | Store/query future embeddings |

Rules:

- routes do not contain SQL;
- services orchestrate business flows;
- repositories use parameterized SQL;
- every query is scoped by authenticated ownership where applicable;
- database telemetry must not record SQL text or bind values.

---

## 20. Security Design

- never commit `.env`;
- never log secrets;
- validate JWT on protected endpoints;
- derive ownership from token `sub`;
- validate uploaded file metadata, size, and content;
- generate safe storage paths;
- use parameterized SQL;
- use ownership-aware foreign keys;
- do not expose raw framework/validation/exception details;
- do not use AI for source-of-truth calculations;
- validate AI output before persistence;
- use bounded metric labels;
- sanitize spans before export.

---

## 21. Quality Gates

CI runs on pull requests to `main` and pushes to `main`.

Checks:

```bash
docker compose config --quiet
docker compose --profile observability config --quiet
docker compose -f docker-compose.test.yml config --quiet
python -m ruff check --output-format=github .
python -m ruff format --check .
python -m bandit -r app
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
python -m pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
python scripts/check_coverage.py coverage.json 95 95
```

Coverage policy:

- line coverage at least 95%;
- branch coverage at least 95%.

Dependency policy:

- runtime dependencies belong in `requirements.txt`;
- test/development dependencies belong in `requirements-dev.txt`;
- both sets are audited;
- vulnerabilities must not be ignored casually.

Observability tests verify both presence and exclusion:

- request outcome fields;
- request-ID consistency;
- route-template and query redaction;
- Problem Details mapping;
- exception containment;
- bounded metrics;
- sanitized span attributes/events/status;
- absence of credentials, concrete paths, query values, raw exception messages, and stack traces.

---

## 22. Future Analytics, AI, RAG, and Agents

### 22.1 Analytics

`analytics_service.py` should own deterministic calculations:

- monthly totals;
- income, spend, and net;
- category breakdown;
- merchant totals;
- empty/no-data behavior.

```text
SQL/backend calculates. AI explains.
```

### 22.2 AI and RAG

- AI access goes through a provider abstraction;
- structured output is schema-validated;
- RAG chunks include `user_id`;
- retrieval filters by `user_id`;
- prompts, retrieved financial data, and responses are not logged by default.

### 22.3 Agents

- agents call predefined tools only;
- agents do not access repositories directly;
- agents do not execute arbitrary SQL;
- tool results are ownership-filtered and validated;
- final financial figures come from deterministic backend tools.
