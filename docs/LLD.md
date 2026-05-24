# Low-Level Design (LLD) — Spend Analyzer

## 1. Purpose

This document describes the low-level backend design for Spend Analyzer.

It focuses on implementation-level details: modules, configuration, API contracts, database schema, validation rules, error handling, service boundaries, and quality gates.

For high-level architecture diagrams, runtime views, major flows, ERD, AI/RAG overview, and deployment view, see [`HLD.md`](HLD.md).

For parser-specific design, see [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

For learning objectives and issue sequencing, see [`LEARNING_GUIDE.md`](LEARNING_GUIDE.md).

---

## 2. Design Status

### Implemented currently

- FastAPI backend application
- Environment-driven configuration with Pydantic Settings
- PostgreSQL connectivity
- Flyway database migrations under `infra/db/migration`
- Local Keycloak/OIDC identity provider setup
- JWT validation and authenticated user context
- `GET /health`
- `GET /health/db`
- `GET /me`
- `POST /ingest` for authenticated PDF upload
- Local file storage for uploaded PDFs
- Statement and transaction schema migrations
- Docker and Docker Compose based local/test runtime
- Strict CI quality gates

### Planned later

- Persist uploaded statement metadata from the ingestion API
- PDF text/table extraction
- Statement detection
- Generic transaction parser
- Broad bank/account parsers
- AI parsing fallback
- Transaction persistence from parsed output
- Rule-based and AI-assisted categorization
- Analytics APIs
- AI insight APIs
- Natural language query layer
- RAG and semantic retrieval
- Controlled finance agent
- Frontend
- Cloud deployment

---

## 3. Repository Structure

Current backend structure:

```text
app/
├── main.py
├── config.py
├── api/
│   ├── health_routes.py
│   ├── ingest_routes.py
│   └── me_routes.py
├── auth/
│   ├── dependencies.py
│   └── jwt_validator.py
├── core/
├── db/
│   └── connection.py
├── models/
├── repositories/
├── schemas/
│   ├── auth_schema.py
│   ├── health_schema.py
│   └── ingest_schema.py
└── services/
    ├── file_storage_service.py
    └── health_service.py
```

Future module additions:

```text
app/parsing/
app/ai/
app/rag/
app/agents/
```

---

## 4. Configuration Design

Configuration is loaded through `app/config.py` using Pydantic Settings.

Other modules should import the typed `settings` object instead of reading environment variables directly.

### Application configuration

```text
APP_NAME
APP_ENV
APP_VERSION
APP_PORT
```

### Database configuration

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

The application derives a PostgreSQL connection URL from these fields.

### Identity provider / OIDC configuration

```text
KEYCLOAK_ADMIN
KEYCLOAK_ADMIN_PASSWORD
OIDC_ISSUER_URL
OIDC_JWKS_URL
OIDC_AUDIENCE
OIDC_CLIENT_ID
```

### AI configuration

```text
OPENAI_API_KEY
OPENAI_MODEL
```

AI is considered enabled only when `OPENAI_API_KEY` is non-blank.

### Storage configuration

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

---

## 5. Authentication and Authorization Design

The backend acts as an OAuth2/OIDC resource server.

The backend does not handle:

- User registration
- Password storage
- Password reset
- Login UI

Those responsibilities belong to the identity provider.

### Backend responsibilities

- Extract bearer token from the request.
- Fetch and cache JWKS keys.
- Validate token signature.
- Verify issuer.
- Verify audience.
- Extract authenticated user data.
- Attach authenticated user context to route handlers.

### User identifier rule

The backend uses the token `sub` claim as the internal user identifier.

```text
user_id = token["sub"]
```

The backend must never accept `user_id` from API payloads for ownership decisions.

---

## 6. API Layer Design

| Module | Current responsibility |
|---|---|
| `health_routes.py` | Application and database health APIs |
| `me_routes.py` | Authenticated user inspection API |
| `ingest_routes.py` | Authenticated PDF upload API |

Future route modules:

| Planned module | Planned responsibility |
|---|---|
| `transaction_routes.py` | Transaction listing and filtering |
| `summary_routes.py` | Monthly summary APIs |
| `comparison_routes.py` | Month-on-month comparison APIs |
| `insight_routes.py` | AI-generated insight APIs |
| `query_routes.py` | Natural language query APIs |

---

## 7. Current API Endpoints

### `GET /health`

Returns application health and service metadata.

Response shape:

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

### `GET /health/db`

Returns application metadata and database health check result.

Successful database check shape:

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

### `GET /me`

Requires a valid bearer token.

Response shape:

```json
{
  "user_id": "oidc-sub",
  "username": "test.user",
  "email": "test.user@example.com"
}
```

### `POST /ingest`

Requires a valid bearer token and `multipart/form-data`.

Request fields:

| Field | Required | Description |
|---|---:|---|
| `file` | Yes | PDF statement file |
| `institution` | No | User-provided institution hint |
| `account_type` | No | User-provided account type hint |
| `account_name` | No | User-friendly account/card name |
| `statement_format` | No | User-provided format hint |

Current response shape:

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

Current behavior:

- Validates authentication.
- Validates PDF metadata.
- Reads file with configured upload-size limit.
- Rejects oversized uploads with 413.
- Rejects invalid uploads with 400.
- Saves the uploaded PDF to local storage.
- Returns upload metadata.

Current limitation:

- The endpoint currently saves the file and returns upload metadata.
- Full statement metadata persistence and parsing pipeline integration are planned follow-up work.

---

## 8. Current Database Schema

### Table: `statements`

Current migration: `infra/db/migration/V2__create_statements_table.sql`.

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

### Table: `transactions`

Current migration: `infra/db/migration/V3__create_transactions_table.sql`.

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

### User isolation rule

Transactions reference statements using a composite ownership-aware foreign key:

```sql
FOREIGN KEY (statement_id, user_id)
REFERENCES statements (id, user_id)
```

This prevents one user's transaction from referencing another user's statement.

---

## 9. Current Upload Implementation

Current upload flow details:

```text
POST /ingest
   |
   v
Validate JWT
   |
   v
Extract AuthenticatedUser
   |
   v
Validate PDF filename/content-type metadata
   |
   v
Read uploaded file in chunks with size limit
   |
   v
Validate file content as PDF-like content
   |
   v
Generate statement_reference UUID
   |
   v
Save PDF to local upload directory
   |
   v
Return StatementUploadResponse
```

Current file-storage responsibilities:

- Reject missing/blank filenames.
- Reject non-PDF extensions.
- Reject non-PDF content types.
- Reject empty files.
- Reject oversized files.
- Reject fake/non-PDF content.
- Generate stored filename from user and statement reference.
- Avoid trusting original file name for storage path identity.

The high-level upload sequence diagram is maintained in [`HLD.md`](HLD.md).

---

## 10. Planned Full Ingestion Implementation

Planned implementation steps:

1. Upload and store PDF.
2. Create statement metadata record.
3. Extract PDF text/tables.
4. Detect statement metadata where possible.
5. Run generic parser.
6. Validate parse result.
7. Run broad bank/account parser if generic confidence is low.
8. Validate parse result.
9. Run AI fallback parser if deterministic confidence remains low.
10. Validate AI candidate transactions.
11. Persist valid transactions or mark statement as `NEEDS_REVIEW`.

Persistence must happen only after validation.

Detailed parser design is maintained in [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md).

---

## 11. Planned Parser Result Model

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

---

## 12. Planned Parse Validation Design

Validation responsibilities:

- Validate required fields.
- Validate dates.
- Validate decimal amounts.
- Validate debit/credit direction.
- Detect duplicate rows.
- Check transaction dates against statement period when available.
- Reconcile totals or balances where available.
- Assign confidence level.

Confidence policy:

```text
HIGH    -> persist transactions
MEDIUM  -> persist valid transactions and mark review_required=true
LOW     -> try next parser layer
FAILED  -> try next parser layer or mark statement NEEDS_REVIEW/FAILED
```

AI fallback must not bypass validation.

---

## 13. Planned Categorization Design

Rule-based categorization should be implemented first.

Examples:

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

Fallback category:

```text
Other
```

Future:

- AI-assisted category fallback
- Merchant normalization
- User-defined category rules

---

## 14. Repository Layer Design

Repository modules should contain database access logic only.

Planned repositories:

| Repository | Responsibility |
|---|---|
| `statement_repository.py` | Insert statements, update status, fetch statement metadata |
| `transaction_repository.py` | Insert/query transactions, aggregate by month/category/merchant |
| `parser_run_repository.py` | Store parser execution attempts and debugging data |
| `vector_repository.py` | Store/query embeddings in future RAG phase |

API routes should not contain SQL.

Services should orchestrate business flow and call repositories.

---

## 15. Error Handling

| Scenario | Status |
|---|---:|
| Missing token | 401 |
| Invalid token | 401 |
| Invalid file type | 400 |
| Upload too large | 413 |
| Invalid PDF content | 400 |
| PDF extraction failed | 422 |
| Parsing failed | 422 |
| Needs manual review | 202 |
| Database unavailable | 503 |
| Unexpected error | 500 |

Rules:

- Return clear API errors.
- Do not expose stack traces.
- Log internal errors.
- Do not log full statement content.
- Do not persist low-confidence AI output without validation.

---

## 16. Logging and Privacy

Log:

- Request start/end where useful.
- File ingestion result.
- Parser selected.
- Parser confidence.
- Number of parsed transactions.
- Database errors.
- AI fallback failures.

Do not log:

- Access tokens.
- API keys.
- Full statement contents.
- Full PDF extracted text.
- Sensitive financial data beyond what is required for debugging.

---

## 17. Security Design

- Never commit `.env`.
- Never log secrets.
- Validate JWT on protected endpoints.
- Always filter data by authenticated `user_id`.
- Validate uploaded file type and content.
- Restrict upload size with `MAX_UPLOAD_SIZE_BYTES`.
- Use parameterized SQL.
- Use ownership-aware foreign keys where possible.
- Do not use AI for source-of-truth financial calculations.
- Validate AI output before persistence.

---

## 18. Quality Gates

CI runs on pull requests to `main` and pushes to `main`.

Current quality checks:

```bash
python -m ruff check --output-format=github .
python -m ruff format --check .
python -m bandit -r app
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
python -m pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
python scripts/check_coverage.py coverage.json 95 95
```

Coverage policy:

- Statement/line coverage must be at least 95%.
- Branch coverage must be at least 95%.

Dependency policy:

- Runtime dependencies live in `requirements.txt`.
- Test/development dependencies live in `requirements-dev.txt`.
- Runtime and development dependencies are both audited.
- No ignored vulnerabilities should be added casually.

Dependabot policy:

- Python dependencies are checked daily.
- GitHub Actions dependencies are checked weekly.

---

## 19. Planned Analytics Design

`analytics_service.py` should own deterministic calculations.

Responsibilities:

- Calculate monthly totals.
- Calculate income, spend, and net.
- Calculate category breakdown.
- Calculate merchant totals.
- Handle empty/no-data scenarios.
- Return structured JSON.

Important rule:

```text
SQL/backend calculates. AI explains.
```

---

## 20. Planned AI, RAG, and Agent Design

Detailed high-level AI/RAG/agent flows are maintained in [`HLD.md`](HLD.md).

Implementation rules for future modules:

- AI access should go through a provider abstraction.
- AI output must be validated with structured schemas.
- RAG chunks must include `user_id`.
- Retrieval must filter by `user_id`.
- SQL/backend tools provide financial numbers.
- AI generates wording from trusted facts and retrieved context.
- Agents can call predefined tools only.
- Agents cannot directly access repositories or execute arbitrary SQL.

---

## 21. MVP Completion Criteria

A mature MVP backend should satisfy:

- Backend runs through Docker.
- Authentication is integrated.
- PostgreSQL is connected.
- Database migrations are repeatable.
- PDF statement upload works.
- Statement metadata is persisted.
- Transactions are parsed and stored.
- Parser failures do not silently corrupt data.
- Low-confidence parsing can be flagged for review.
- Data is isolated per user.
- Monthly summary API works.
- AI insights are generated from deterministic backend facts.
- Quality gates pass on every PR and main merge.
