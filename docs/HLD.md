# High-Level Design (HLD) — Spend Analyzer

## 1. Purpose

This document describes the high-level architecture of Spend Analyzer.

It covers the major system components, runtime relationships, observability architecture, system boundaries, and important end-to-end flows. Detailed module behavior belongs in [`LLD.md`](LLD.md). Observability implementation decisions belong in [`OBSERVABILITY_LLD.md`](OBSERVABILITY_LLD.md). Operational procedures belong in [`LOCAL_OBSERVABILITY.md`](LOCAL_OBSERVABILITY.md). Parser-specific design belongs in [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

---

## 2. Architecture Goals

Spend Analyzer is designed to be:

- secure by default;
- multi-user from the beginning;
- backend-calculation-first for financial correctness;
- AI-assisted but not AI-dependent;
- observable through structured logs, bounded metrics, and safe traces;
- containerized for local development and future cloud deployment;
- learning-friendly, with explicit separation between current and planned capabilities.

Core rule:

```text
SQL/backend calculates.
Backend validates.
AI assists and explains.
Telemetry must remain safe.
```

---

## 3. System Context Diagram

```mermaid
flowchart LR
    User[User]
    Client[Client / API caller]
    API[FastAPI backend]
    IdP[OIDC identity provider / Keycloak]
    DB[(PostgreSQL)]
    Files[(Local file storage)]
    Metrics[Prometheus]
    Collector[OpenTelemetry Collector]
    Traces[Tempo]
    Dashboards[Grafana]
    AI[Future AI provider]
    Vector[(Future vector store)]

    User --> Client
    Client -->|Bearer token + API requests| API
    Client -->|Login / token request| IdP
    API -->|Validate JWT / fetch JWKS| IdP
    API -->|Read/write metadata and transactions| DB
    API -->|Store uploaded PDFs| Files
    Metrics -->|Scrape application metrics| API
    Metrics -->|Scrape PostgreSQL metrics| DB
    API -->|OTLP traces| Collector
    Collector --> Traces
    Dashboards --> Metrics
    Dashboards --> Traces
    API -.->|Future parsing fallback / insights| AI
    API -.->|Future semantic retrieval| Vector
```

The user-facing application remains independent of the optional local observability backend. Metrics and traces are operational outputs and are not required for business request processing.

---

## 4. Current Container View

```mermaid
flowchart TB
    subgraph CoreRuntime[Core local Docker runtime]
        App[FastAPI app]
        Db[(PostgreSQL)]
        Keycloak[Keycloak identity provider]
        Flyway[Flyway migration runner]
        Uploads[(Upload directory)]
    end

    subgraph OptionalObservability[Optional observability profile]
        Collector[OpenTelemetry Collector]
        Prometheus[Prometheus]
        Grafana[Grafana]
        Tempo[Tempo]
        PgExporter[PostgreSQL exporter]
    end

    App --> Db
    App --> Keycloak
    App --> Uploads
    Flyway --> Db
    Keycloak -->|realm import| Realm[Local realm JSON]

    Prometheus -->|scrape /metrics| App
    PgExporter --> Db
    Prometheus -->|scrape exporter metrics| PgExporter
    App -->|OTLP traces| Collector
    Collector --> Tempo
    Grafana --> Prometheus
    Grafana --> Tempo
```

| Service | Responsibility | Required for normal startup |
|---|---|---:|
| `app` | FastAPI backend | Yes |
| `db` | PostgreSQL database | Yes |
| `identity-provider` | Local Keycloak/OIDC provider | Yes |
| `flyway` | Applies SQL migrations | Yes, one-shot |
| upload storage | Stores uploaded PDFs locally | Yes |
| `otel-collector` | Receives, batches, and forwards OTLP traces | No |
| `prometheus` | Scrapes and stores application/database metrics | No |
| `grafana` | Explores metrics and traces | No |
| `tempo` | Stores local traces | No |
| `postgres-exporter` | Exposes PostgreSQL operational metrics | No |

The optional services start with:

```text
docker compose --profile observability up --build -d
```

---

## 5. Backend Component Diagram

```mermaid
flowchart TB
    Routes[API routes]
    Auth[Auth dependency + JWT validator]
    Services[Application services]
    Storage[File storage service]
    DbConn[Database connection]
    Errors[Typed application errors]
    ProblemDetails[Central Problem Details handlers]
    Middleware[Request context middleware]
    Metrics[Bounded application metrics]
    Tracing[Automatic HTTP tracing + span sanitization]
    Schemas[Pydantic schemas]
    Settings[Typed settings]
    DB[(PostgreSQL)]
    Files[(Uploaded files)]

    Routes --> Auth
    Routes --> Services
    Routes --> Storage
    Routes --> Schemas
    Routes --> Errors
    Routes --> Metrics

    Auth --> Errors
    Auth --> Metrics
    Auth --> Settings

    Services --> DbConn
    Services --> Settings
    Storage --> Files
    Storage --> Errors
    Storage --> Settings
    DbConn --> DB

    Errors --> ProblemDetails
    Middleware --> ProblemDetails
    Middleware --> Tracing
    Tracing --> Settings
    Metrics --> Settings
```

Application routes and services do not create OpenTelemetry spans. They raise typed failures and record bounded business metrics where aggregation is useful. Common infrastructure owns request correlation, HTTP outcome logging, Problem Details conversion, and HTTP tracing.

### 5.1 Current route modules

| Module | Responsibility |
|---|---|
| `health_routes.py` | Application and database health checks |
| `me_routes.py` | Authenticated user details |
| `ingest_routes.py` | Authenticated PDF upload |

### 5.2 Current cross-cutting modules

| Module | Responsibility |
|---|---|
| `errors.py` | Typed controlled application failures and safe diagnostic context |
| `http.py` | Route-template resolution and safe request/URL sanitization |
| `problem_details.py` | Central exception mapping, diagnostic logging, and RFC 9457-compatible responses |
| `observability/context.py` | Request correlation context |
| `observability/logging.py` | Structured JSON logging and safe processors |
| `observability/middleware.py` | Request ID, duration, exception containment, and one HTTP outcome log |
| `observability/metrics.py` | HTTP, application, dependency, auth, storage, and ingestion metrics |
| `observability/tracing.py` | Automatic FastAPI/outbound HTTP tracing and pre-export span sanitization |

### 5.3 Planned component additions

| Component | Responsibility |
|---|---|
| `repositories/` | Database access abstractions |
| `parsing/` | PDF extraction, statement detection, and transaction parsing |
| `ai/` | AI provider abstraction and structured-output utilities |
| `rag/` | Chunking, embeddings, retrieval, and context construction |
| `agents/` | Controlled tool-based finance agent |

---

## 6. Observability Architecture

### 6.1 Signal flows

```text
Logs:
FastAPI -> structured JSON -> container stdout

Metrics:
FastAPI /metrics -------------------+
                                     +-> Prometheus -> Grafana
PostgreSQL exporter /metrics -------+

Traces:
FastAPI automatic spans
    -> sanitizing span processor
    -> OTLP
    -> OpenTelemetry Collector
    -> Tempo
    -> Grafana
```

Prometheus directly scrapes Prometheus-format metrics. The Collector transports and batches traces; it is not a metrics database.

### 6.2 Request lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant Middleware as Request middleware
    participant Route as Route / dependency / service
    participant Handler as Central exception handler
    participant Trace as Automatic tracing
    participant Logs as Structured logs

    Client->>Middleware: HTTP request
    Middleware->>Middleware: Validate/generate request_id
    Middleware->>Trace: Automatic server span exists
    Middleware->>Route: Dispatch request
    alt Successful
        Route-->>Middleware: Response
    else Controlled ApplicationError
        Route-->>Handler: Typed exception
        Handler->>Logs: Safe diagnostic event
        Handler-->>Middleware: Problem Details response
    else Unexpected exception
        Middleware->>Handler: Contain exception
        Handler->>Logs: Generic bounded diagnostic
        Handler-->>Middleware: Safe 500 Problem Details
    end
    Middleware->>Logs: One http.request outcome with status and duration
    Middleware-->>Client: Response + X-Request-ID
```

The middleware owns request-wide mechanics. Typed exceptions describe controlled failures. Central handlers own error mapping and diagnostic logs. Automatic instrumentation owns HTTP spans.

### 6.3 Request correlation

Each request can have:

- `request_id`: client-facing support identifier returned through `X-Request-ID`;
- `trace_id`: distributed trace identifier when tracing is enabled;
- `span_id`: current span identifier when tracing is enabled.

Request, trace, and span identifiers are log fields only. They are never Prometheus labels.

### 6.4 Safe request target

Request logs, Problem Details, and server-span HTTP attributes use:

- route templates instead of concrete dynamic path values;
- bounded query parameter names;
- `[REDACTED]` for every query value;
- no scheme, host, port, fragment, headers, or body.

Examples:

```text
/items/{item_id}
/items/{item_id}?source=%5BREDACTED%5D
/<unmatched>?source=%5BREDACTED%5D
```

### 6.5 Safe telemetry boundary

Telemetry must not contain:

- passwords, tokens, API keys, authorization headers, or identity claims;
- raw user identifiers, usernames, or email addresses;
- database URLs, credentials, SQL, or bind values;
- concrete dynamic path values or query values;
- raw exception messages or stack traces;
- original sensitive filenames;
- statement contents, extracted text, account numbers, card numbers, or user-provided financial descriptions;
- identity-provider payloads or provider URLs in generic outbound traces.

The application records bounded categories, exception class names, generated statement references, sizes, counts, and configured limits where operationally useful.

### 6.6 Tracing decision

Issue #78 uses automatic infrastructure tracing:

- `FastAPIInstrumentor` creates incoming server spans;
- `RequestsInstrumentor` creates supported outbound HTTP client spans;
- configured identity-provider issuer and JWKS endpoints are excluded from generic outbound tracing;
- completed spans are sanitized before batching and OTLP export;
- application routes and services do not import OpenTelemetry or create manual spans;
- future business/dependency spans require a separate design decision.

### 6.7 Centralized log search

OpenSearch, Elasticsearch/ELK, and Loki are deferred. Structured JSON logs to stdout are sufficient for the current MVP. A centralized backend should be added only when retention, multi-instance search, or incident-investigation needs justify its operational cost.

---

## 7. Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant IdP as OIDC / Keycloak
    participant API as FastAPI backend
    participant Metrics as Prometheus metrics
    participant Handler as Problem Details handler

    User->>Client: Authenticate
    Client->>IdP: Login / token request
    IdP-->>Client: Access token
    Client->>API: Protected API request

    alt Credentials missing
        API->>Metrics: Increment missing_credentials
        API->>Handler: AuthenticationRequiredError
        Handler-->>Client: 401 Problem Details + WWW-Authenticate
    else Token supplied
        API->>IdP: Fetch JWKS when cache is empty
        alt Identity provider unavailable or response unusable
            API->>Metrics: Set identity_provider health to 0
            API->>Handler: IdentityProviderUnavailableError
            Handler-->>Client: 503 Problem Details
        else Signing keys available
            IdP-->>API: Public signing keys
            API->>API: Validate signature, issuer, audience, expiry
            alt Token invalid
                API->>Metrics: Increment credentials_invalid
                API->>Handler: InvalidCredentialsError
                Handler-->>Client: 401 Problem Details + WWW-Authenticate
            else Token valid
                API->>API: Derive user_id from sub
                API-->>Client: Authenticated response
            end
        end
    end
```

Security rules:

- backend ownership is derived from token `sub`;
- the backend never accepts user ownership from request payload;
- protected routes require a valid bearer token;
- issuer and audience must match configured values;
- invalid credentials and identity-provider outages are separate operational categories;
- identity-provider unavailability returns `503` and does not increment authentication-failure metrics;
- tokens, claims, key IDs, provider payloads, and raw validation messages are not telemetry fields.

---

## 8. Current Statement Upload Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI /ingest
    participant Auth as JWT validation
    participant Storage as File storage service
    participant Disk as Local upload storage
    participant Metrics as Bounded metrics
    participant Handler as Problem Details handler

    Client->>API: POST /ingest with PDF + optional hints
    API->>Auth: Validate bearer token
    Auth-->>API: Authenticated user context
    API->>API: Generate statement_reference
    API->>Metrics: Record ingestion attempt
    API->>API: Validate metadata and read with size limit
    API->>Storage: Save validated PDF
    Storage->>Disk: Write generated filename under hashed user directory

    alt Invalid PDF
        API->>Metrics: Record invalid_pdf
        API->>Handler: InvalidPdfError
        Handler-->>Client: 400 Problem Details
    else Upload too large
        API->>Metrics: Record upload_too_large
        API->>Handler: UploadTooLargeError
        Handler-->>Client: 413 Problem Details
    else Storage unavailable
        Disk-->>Storage: OSError
        Storage-->>API: FileStorageUnavailableError
        API->>Metrics: Record storage and ingestion failure
        API->>Handler: Typed exception with safe context
        Handler-->>Client: 503 Problem Details
    else Internal storage defect
        Storage-->>API: FileStorageError
        API->>Metrics: Record bounded internal failure
        API->>Handler: Typed exception with safe context
        Handler-->>Client: 500 Problem Details
    else Stored
        Disk-->>Storage: Stored file path
        Storage-->>API: Generated stored filename and path
        API->>Metrics: Record success and upload-size observation
        API-->>Client: 201 upload metadata response
    end
```

Current behavior:

- authentication is required;
- metadata and PDF-like content are validated;
- the upload is read in bounded chunks with a configured limit;
- generated storage paths do not use the original filename or raw user ID;
- oversized uploads return `413`;
- invalid PDFs return `400`;
- storage availability failures return `503`;
- unexpected internal storage failures return a safe `500`;
- metrics use bounded categories;
- the route emits one meaningful success business event;
- the incoming request is traced automatically; the route does not create a manual ingestion span;
- statement metadata persistence and parsing integration are planned next.

---

## 9. Future Full Ingestion and Parsing Flow

```mermaid
flowchart TD
    Upload[Upload PDF] --> Store[Store original PDF]
    Store --> StatementRecord[Create statement metadata]
    StatementRecord --> Extract[Extract text and tables]
    Extract --> Detect[Detect institution/account/format]
    Detect --> Generic[Generic parser]
    Generic --> ValidateGeneric[Validate parse result]
    ValidateGeneric -->|High confidence| Persist[Persist transactions]
    ValidateGeneric -->|Low confidence| BankParser[Broad bank/account parser]
    BankParser --> ValidateBank[Validate parse result]
    ValidateBank -->|High confidence| Persist
    ValidateBank -->|Low confidence| AIFallback[AI fallback parser]
    AIFallback --> ValidateAI[Validate AI candidate transactions]
    ValidateAI -->|Valid| Persist
    ValidateAI -->|Low confidence / invalid| Review[Mark statement NEEDS_REVIEW]
```

Design rules:

- generic parsing precedes specialized parsing;
- bank/account parsers should be broad rather than product-specific unless necessary;
- AI fallback produces candidate data only;
- backend validation decides whether data can be persisted;
- every future stage must deliberately choose baseline telemetry, a structured event, bounded metrics, a justified custom span, or no additional telemetry.

Detailed parser design is maintained in [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

---

## 10. Current Database ERD

```mermaid
erDiagram
    STATEMENTS ||--o{ TRANSACTIONS : owns

    STATEMENTS {
        uuid id PK
        text user_id UK
        text institution
        text account_type
        text account_name
        text statement_format
        text original_file_name
        text stored_file_path
        text status
        numeric parse_confidence
        boolean review_required
        timestamptz uploaded_at
    }

    TRANSACTIONS {
        uuid id PK
        text user_id
        uuid statement_id FK
        date transaction_date
        text description
        text merchant
        text category
        numeric amount
        text transaction_type
        text institution
        text account_type
        text account_name
        text source_parser
        numeric confidence_score
        timestamptz created_at
    }
```

Ownership rule:

```text
transactions(statement_id, user_id) references statements(id, user_id)
```

This prevents one user's transaction from referencing another user's statement.

Database observability currently uses:

- the automatic incoming request trace for `/health/db`;
- the bounded database dependency-health gauge;
- PostgreSQL exporter connection, activity, lock, and database metrics.

There is no manual `database.health_check` child span. Future repository work may add database instrumentation only after dependency compatibility, query patterns, and sanitization rules are validated. SQL, bind values, credentials, and financial data must never be recorded.

---

## 11. Future AI and RAG Architecture

```mermaid
flowchart LR
    Query[User question]
    Router[Intent classifier / query router]
    SQLTools[Deterministic SQL-backed tools]
    Retriever[User-filtered retrieval service]
    Vector[(Vector store)]
    AI[AI provider]
    Answer[Grounded answer]

    Query --> Router
    Router --> SQLTools
    Router --> Retriever
    Retriever --> Vector
    SQLTools --> AI
    Retriever --> AI
    AI --> Answer
```

Rules:

- SQL/backend tools provide financial numbers;
- retrieval is filtered by authenticated `user_id`;
- AI generates explanations from trusted facts and retrieved context;
- AI must not execute raw SQL;
- AI must not calculate final financial totals;
- prompts, retrieved financial content, and model responses are not logged by default.

---

## 12. Future Controlled Agent Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as Query API
    participant Agent as Finance agent
    participant Tools as Registered backend tools
    participant DB as PostgreSQL
    participant AI as AI provider

    Client->>API: Ask finance question
    API->>Agent: Create plan
    Agent->>Tools: Select allowed tool
    Tools->>DB: Execute user-filtered query
    DB-->>Tools: Trusted facts
    Tools-->>Agent: Observation
    Agent->>AI: Generate response from observations
    AI-->>Agent: Draft answer
    Agent-->>API: Validated answer
    API-->>Client: Response
```

Agent boundary:

```text
The agent can call predefined tools only.
The agent cannot directly access repositories or execute arbitrary SQL.
```

---

## 13. Deployment View

### 13.1 Current local deployment

```text
Docker Compose
├── app
├── db
├── identity-provider
├── flyway
├── upload storage
└── observability profile
    ├── otel-collector
    ├── prometheus
    ├── grafana
    ├── tempo
    └── postgres-exporter
```

The observability profile is optional. The application must start and process requests when it is disabled.

### 13.2 Future cloud mapping

| Local component | Future cloud equivalent |
|---|---|
| FastAPI app container | ECS, Kubernetes, or equivalent |
| PostgreSQL container | Managed PostgreSQL |
| Local upload directory | Object storage |
| Local Keycloak | Managed or self-hosted OIDC provider |
| Prometheus | Managed Prometheus-compatible backend |
| Tempo | Managed or self-hosted trace backend |
| OpenTelemetry Collector | Sidecar, daemon, or gateway Collector |
| Grafana | Managed or self-hosted visualization |
| Docker Compose | Infrastructure as code / orchestration |
| Local env file | Secret and parameter management |

Before cloud deployment, introduce a storage abstraction so local filesystem and object storage implementations share the same service contract.

---

## 14. Documentation Responsibility

| Document | Responsibility |
|---|---|
| `HLD.md` | Major components, interactions, runtime views, major flows, ERD, and deployment view |
| `LLD.md` | Module details, API contracts, validation, error handling, and service/repository rules |
| `OBSERVABILITY_LLD.md` | Detailed logging, metrics, tracing, correlation, and telemetry-safety decisions |
| `LOCAL_OBSERVABILITY.md` | Local startup, metric/trace inspection, request-ID debugging, and runbooks |
| `PARSING_STRATEGY.md` | Parser strategy, confidence policy, AI fallback, and manual review |
| `LEARNING_GUIDE.md` | Learning objectives, phases, and issue-quality expectations |
| `PROJECT_REQUIREMENTS.md` | Product scope and functional/non-functional requirements |

---

## 15. Current Design Summary

```text
FastAPI
+ centralized typed error handling and Problem Details
+ Keycloak/OIDC
+ PostgreSQL/Flyway
+ secure local PDF upload
+ structured request-correlated logs
+ bounded Prometheus metrics
+ automatically generated and sanitized OpenTelemetry traces
+ optional local observability stack
+ strict CI gates
```

Next product architecture step:

```text
Persist statement metadata, then add PDF extraction and the parsing pipeline.
```

Future feature work must reuse the current request correlation, error handling, metric registry, and tracing provider rather than creating parallel infrastructure.
