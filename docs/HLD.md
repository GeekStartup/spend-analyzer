# High-Level Design (HLD) — Spend Analyzer

## 1. Purpose

This document describes the high-level architecture of Spend Analyzer.

The HLD explains the major system components, runtime relationships, system boundaries, and important end-to-end flows. Detailed module-level behavior belongs in [`LLD.md`](LLD.md). Parser-specific design belongs in [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

---

## 2. Architecture Goals

Spend Analyzer is designed to be:

- Secure by default.
- Multi-user from the beginning.
- Backend-calculation-first for financial correctness.
- AI-assisted but not AI-dependent.
- Containerized for local development and future cloud deployment.
- Learning-friendly, with explicit separation between current implementation and planned capabilities.

Core rule:

```text
SQL/backend calculates.
Backend validates.
AI assists and explains.
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
    AI[Future AI provider]
    Vector[(Future vector store)]

    User --> Client
    Client -->|Bearer token + API requests| API
    Client -->|Login / token request| IdP
    API -->|Validate JWT / JWKS| IdP
    API -->|Read/write metadata and transactions| DB
    API -->|Store uploaded PDFs| Files
    API -.->|Future parsing fallback / insights| AI
    API -.->|Future semantic retrieval| Vector
```

---

## 4. Current Container View

```mermaid
flowchart TB
    subgraph LocalRuntime[Local Docker runtime]
        App[FastAPI app container]
        Db[(PostgreSQL container)]
        Keycloak[Keycloak identity-provider container]
        Flyway[Flyway migration runner]
        Uploads[(Uploads volume / directory)]
    end

    App --> Db
    App --> Keycloak
    App --> Uploads
    Flyway --> Db
    Keycloak -->|realm import| Realm[Local realm JSON]
```

Current local services:

| Service | Responsibility |
|---|---|
| `app` | FastAPI backend |
| `db` | PostgreSQL database |
| `identity-provider` | Local Keycloak/OIDC provider |
| migration runner | Applies SQL migrations under `infra/db/migration` |
| upload storage | Stores uploaded PDF files locally |

---

## 5. Backend Component Diagram

```mermaid
flowchart TB
    Routes[API routes]
    Auth[Auth dependencies + JWT validator]
    Schemas[Pydantic schemas]
    Services[Application services]
    Storage[File storage service]
    DbConn[Database connection]
    Settings[Configuration settings]
    DB[(PostgreSQL)]
    Files[(Uploaded files)]

    Routes --> Auth
    Routes --> Schemas
    Routes --> Services
    Routes --> Storage
    Services --> DbConn
    Storage --> Files
    DbConn --> DB
    Auth --> Settings
    Services --> Settings
    Storage --> Settings
```

Current implemented route modules:

| Module | Responsibility |
|---|---|
| `health_routes.py` | Application and database health checks |
| `me_routes.py` | Authenticated user details |
| `ingest_routes.py` | Authenticated PDF upload |

Planned component additions:

| Component | Responsibility |
|---|---|
| `repositories/` | Database access abstractions |
| `parsing/` | PDF extraction, statement detection, transaction parsing |
| `ai/` | AI provider abstraction and structured-output utilities |
| `rag/` | Chunking, embeddings, retrieval, context building |
| `agents/` | Controlled tool-based finance agent |

---

## 6. Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant IdP as OIDC / Keycloak
    participant API as FastAPI backend

    User->>Client: Open app / API client
    Client->>IdP: Authenticate user
    IdP-->>Client: Access token
    Client->>API: API request with bearer token
    API->>IdP: Fetch JWKS if not cached
    IdP-->>API: Public signing keys
    API->>API: Validate signature, issuer, audience
    API->>API: Extract sub, username, email
    API-->>Client: Authenticated response
```

Security rules:

- Backend derives `user_id` from token `sub`.
- Backend never accepts user ownership from request payload.
- Protected routes require a valid bearer token.
- JWT issuer and audience must match configured values.

---

## 7. Current Statement Upload Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI /ingest
    participant Auth as JWT validation
    participant Storage as File storage service
    participant Disk as Local upload storage

    Client->>API: POST /ingest with PDF + optional metadata hints
    API->>Auth: Validate bearer token
    Auth-->>API: Authenticated user context
    API->>API: Validate filename and content type
    API->>API: Read file in chunks with size limit
    API->>Storage: Save validated PDF
    Storage->>Disk: Write generated stored file name
    Disk-->>Storage: Stored file path
    Storage-->>API: Stored file name and path
    API-->>Client: Upload metadata response
```

Current behavior:

- The API authenticates the caller.
- The API validates and stores a PDF statement.
- The API returns upload metadata.
- Statement metadata persistence and parsing integration are planned next steps.

For the exact API contract, request fields, response shape, and status-code behavior, see [`LLD.md`](LLD.md).

---

## 8. Future Full Ingestion and Parsing Flow

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

- Generic parser runs before specialized parser.
- Bank/account parser should be broad, not card-product-specific, unless necessary.
- AI fallback is candidate extraction only.
- Backend validation decides whether data can be persisted.

Detailed parser design is maintained in [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

---

## 9. Current Database ERD

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

Important data-isolation rule:

```text
transactions(statement_id, user_id) references statements(id, user_id)
```

This prevents a transaction for one user from referencing another user's statement.

Detailed table definitions, constraints, and indexes are maintained in [`LLD.md`](LLD.md).

---

## 10. Future AI and RAG Architecture

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

- SQL/backend tools provide financial numbers.
- RAG retrieves context only for the authenticated user.
- AI generates explanation from trusted facts and retrieved context.
- AI must not execute raw SQL.
- AI must not calculate final financial totals.

---

## 11. Future Controlled Agent Flow

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

## 12. Deployment View

### Current local deployment

```text
Docker Compose
├── app
├── db
├── identity-provider
└── migration runner
```

### Future AWS mapping

| Local component | Future AWS equivalent |
|---|---|
| FastAPI app container | ECS / EC2 |
| PostgreSQL container | RDS PostgreSQL |
| Local upload directory | S3 |
| Local Keycloak | Managed or self-hosted OIDC provider |
| Docker Compose | ECS task definitions / IaC |
| Local env file | Secrets Manager / Parameter Store |

Before cloud deployment, introduce a storage abstraction so local filesystem and S3 use the same service interface.

---

## 13. HLD vs LLD Responsibility

| Document | Responsibility |
|---|---|
| `HLD.md` | Major components, system interactions, runtime view, sequence diagrams, ERD, deployment view |
| `LLD.md` | Module details, current API contracts, configuration, validations, table details, service/repository rules |
| `PARSING_STRATEGY.md` | Parser-specific design, confidence strategy, AI fallback and manual review policy |
| `LEARNING_GUIDE.md` | Learning objectives, learning phases, issue-quality expectations |
| `PROJECT_REQUIREMENTS.md` | Product scope, functional requirements, non-functional requirements |

---

## 14. Current Design Summary

Current backend foundation:

```text
FastAPI + Keycloak/OIDC + PostgreSQL + Flyway + local PDF upload + strict CI gates
```

Next architectural step:

```text
Persist statement metadata, then add PDF extraction and parsing pipeline.
```
