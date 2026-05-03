# Low-Level Design (LLD) — Spend Analyzer

## 1. Purpose

This document describes the low-level design for **Spend Analyzer**, a secure personal finance backend system.

The system ingests bank and credit card statements, extracts transactions, validates parsed output, stores transactions securely, and provides analytics and AI-assisted insights.

---

## 2. Scope

This LLD focuses on the backend design for the following capabilities:

- User authentication using OAuth2 / OIDC
- User-level data isolation
- PDF statement ingestion
- Generic and bank-specific transaction parsing
- AI-assisted parsing fallback
- Transaction validation before persistence
- PostgreSQL persistence
- Monthly and category-wise analytics
- AI-generated insights in later MVPs
- Future extensibility for RAG, automation, and frontend integration

---

## 3. System Context

```text
User / Client
    |
    | HTTP API Requests
    v
FastAPI Backend
    |
    | Validate JWT
    v
Identity Provider (OIDC)
    |
    | User context
    v
Business Services
    |
    | Persist / Query
    v
PostgreSQL
    |
    | Optional future context
    v
AI / RAG Layer
```

---

## 4. Core Design Principles

- Keep authentication externalized through an identity provider.
- Never trust client-provided user identifiers.
- Always derive `user_id` from the validated token.
- Store financial data in PostgreSQL.
- Use SQL/backend logic for calculations.
- Use generic parsing first, bank-specific parsing second, and AI parsing fallback only when deterministic parsing fails or confidence is low.
- Validate all parsed transactions before persistence.
- Do not silently persist low-confidence AI output.
- Use AI for fallback, categorization, explanation, and future query intelligence.
- Keep modules small and independently testable.
- Make all environment-specific values configurable.
- Avoid hardcoded secrets.

---

## 5. Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python, FastAPI |
| Database | PostgreSQL |
| Authentication | OAuth2 / OIDC Provider |
| Containerization | Docker, Docker Compose |
| PDF Extraction | pdfplumber |
| AI Provider | OpenAI GPT API |
| Future RAG | pgvector / vector search |
| Future Frontend | React / Vite |

---

## 6. Project Structure

```text
spend-analyzer/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   ├── auth/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── parsing/
│       ├── __init__.py
│       ├── models.py
│       ├── pdf_extractor.py
│       ├── statement_detector.py
│       ├── generic_parser.py
│       ├── parse_validator.py
│       ├── ai_fallback_parser.py
│       └── bank_parsers/
│           ├── __init__.py
│           ├── base_bank_parser.py
│           ├── hdfc_credit_card_parser.py
│           ├── axis_credit_card_parser.py
│           ├── indusind_credit_card_parser.py
│           ├── hdfc_savings_parser.py
│           └── axis_savings_parser.py
├── docs/
│   ├── LLD.md
│   └── MVP_ROADMAP.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
└── .gitignore
```

---

## 7. Configuration Design

All configuration should be loaded from environment variables.

### Configuration Groups

#### Application

```text
APP_NAME
APP_ENV
APP_VERSION
APP_PORT
```

#### Database

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

#### Authentication

```text
KEYCLOAK_ADMIN
KEYCLOAK_ADMIN_PASSWORD
OIDC_ISSUER_URL
OIDC_JWKS_URL
OIDC_AUDIENCE
OIDC_CLIENT_ID
```

#### AI

```text
AI_PROVIDER
OPENAI_API_KEY
OPENAI_MODEL
```

#### File Storage

```text
UPLOAD_DIR
STORAGE_TYPE
```

Future AWS-related configuration:

```text
AWS_REGION
S3_BUCKET_NAME
```

---

## 8. Authentication and Authorization Design

The backend acts as a **resource server**.

It does not handle:

- User registration
- Password storage
- Password reset
- Login UI

These responsibilities belong to the identity provider.

### Backend Responsibilities

- Validate incoming JWT access token
- Verify token signature
- Verify issuer
- Verify audience
- Extract user identity from token
- Attach authenticated user context to request

### User Identifier

The system uses the OIDC `sub` claim as the primary user identifier.

```text
user_id = token["sub"]
```

### Important Rule

The backend must never accept `user_id` from API request payloads for data ownership.

---

## 9. OAuth Flow

The frontend should use **Authorization Code Flow with PKCE**.

```text
1. User opens frontend.
2. Frontend redirects user to identity provider login.
3. User logs in.
4. Identity provider redirects back with authorization code.
5. Frontend exchanges code + PKCE verifier for tokens.
6. Frontend calls FastAPI using Authorization: Bearer <access_token>.
7. FastAPI validates JWT and extracts user identity.
```

Avoid:

- Implicit flow
- Password grant
- Client credentials for user login

---

## 10. API Layer Design

| Module | Responsibility |
|---|---|
| `health_routes.py` | Health checks |
| `ingestion_routes.py` | PDF upload and ingestion |
| `transactions_routes.py` | Transaction listing/filtering |
| `summary_routes.py` | Monthly summary APIs |
| `comparison_routes.py` | Month-on-month comparison |
| `insights_routes.py` | AI-generated insights |

---

## 11. API Endpoints

### Health

```http
GET /health
```

Response:

```json
{
  "status": "OK",
  "service": "Spend Analyzer",
  "environment": "local",
  "version": "0.1.0"
}
```

### DB Health

```http
GET /health/db
```

Response:

```json
{
  "database": "connected"
}
```

### Current User

```http
GET /me
Authorization: Bearer <token>
```

Response:

```json
{
  "user_id": "oidc-sub",
  "email": "user@example.com"
}
```

### Ingest Statement

```http
POST /ingest
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

Request:

- `file`: PDF statement
- `institution`: optional in early MVP, e.g. `hdfc`, `axis`, `indusind`
- `account_type`: optional in early MVP, e.g. `credit_card`, `savings_account`
- `account_name`: optional user-friendly account/card name
- `statement_format`: optional hint when user knows the format

Response:

```json
{
  "status": "success",
  "statement_id": "uuid",
  "transactions_ingested": 42,
  "parse_confidence": 0.92,
  "review_required": false
}
```

### Monthly Summary

```http
GET /summary?month=YYYY-MM
Authorization: Bearer <token>
```

### Month-on-Month Comparison

```http
GET /comparison?month=YYYY-MM
Authorization: Bearer <token>
```

### AI Insights

```http
GET /insights?month=YYYY-MM
Authorization: Bearer <token>
```

---

## 12. Data Model

### Table: `statements`

Stores uploaded statement metadata.

```sql
CREATE TABLE statements (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    institution TEXT,
    account_type TEXT,
    account_name TEXT,
    statement_format TEXT,
    statement_period_from DATE,
    statement_period_to DATE,
    original_file_name TEXT NOT NULL,
    stored_file_path TEXT NOT NULL,
    status TEXT NOT NULL,
    parse_confidence NUMERIC(5, 4),
    review_required BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `transactions`

Stores normalized financial transactions.

```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    statement_id UUID REFERENCES statements(id),
    transaction_date DATE NOT NULL,
    description TEXT NOT NULL,
    merchant TEXT,
    merchant_category TEXT,
    category TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    transaction_type TEXT NOT NULL,
    institution TEXT,
    account_type TEXT,
    account_name TEXT,
    source_parser TEXT,
    confidence_score NUMERIC(5, 4),
    reference_number TEXT,
    reward_points INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `parser_runs`

Stores parser execution history for debugging and auditability.

```sql
CREATE TABLE parser_runs (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    statement_id UUID REFERENCES statements(id),
    parser_name TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence_score NUMERIC(5, 4),
    extracted_transaction_count INTEGER DEFAULT 0,
    warnings TEXT,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Indexes

```sql
CREATE INDEX idx_transactions_user_date
ON transactions (user_id, transaction_date);

CREATE INDEX idx_transactions_user_category
ON transactions (user_id, category);

CREATE INDEX idx_transactions_user_merchant
ON transactions (user_id, merchant);

CREATE INDEX idx_statements_user_status
ON statements (user_id, status);
```

---

## 13. Data Isolation Design

Every query must include user filtering.

Example:

```sql
SELECT *
FROM transactions
WHERE user_id = :current_user_id;
```

No endpoint should return data without applying `user_id`.

---

## 14. Ingestion Flow

```text
POST /ingest
   |
   | Validate JWT
   v
Extract user_id
   |
   v
Validate PDF file
   |
   v
Save file
   |
   v
Create statement record
   |
   v
Extract PDF text/tables
   |
   v
Detect statement metadata where possible
   |
   v
Run generic parser
   |
   v
Validate parse result
   |
   | confidence low
   v
Run bank-specific parser if supported
   |
   v
Validate parse result
   |
   | confidence still low
   v
Run AI fallback parser
   |
   v
Validate AI candidate transactions
   |
   v
Persist valid transactions OR mark statement as NEEDS_REVIEW
```

---

## 15. PDF Extraction Design

### `pdf_extractor.py`

Responsibilities:

- Open PDF file
- Extract text
- Extract tables where available
- Return raw extracted content
- Avoid logging sensitive statement contents

MVP approach:

- Use deterministic extraction first
- Handle invalid PDFs gracefully
- Do not rely only on AI for extraction

---

## 16. Statement Detection Design

### `statement_detector.py`

Responsibilities:

- Detect institution where possible
- Detect account type where possible
- Detect broad statement format where possible
- Use user-supplied hints when present

Known examples:

| Marker | Detected Format |
|---|---|
| `Swiggy HDFC Bank Credit Card Statement` | HDFC credit card |
| `UPI RuPay Credit Card Statement` | HDFC credit card |
| `Flipkart Axis Bank Credit Card Statement` | Axis credit card |
| `INDUSIND BANK LEGEND CREDIT CARD STATEMENT` | IndusInd credit card |

---

## 17. Transaction Parsing Design

### Parsing strategy

```text
Generic Parser → Bank-Specific Parser → AI Fallback Parser → Manual Review
```

### Generic Parser

The generic parser should identify common transaction patterns:

- Dates
- Descriptions
- Amounts
- `Dr` / `Cr` suffixes
- `+` credit indicators
- Withdrawal/deposit columns in savings statements

### Bank-Specific Parsers

Bank-specific parsers should handle broad bank/account quirks, not every individual card variant.

Initial bank parsers:

- `HdfcCreditCardParser`
- `AxisCreditCardParser`
- `IndusindCreditCardParser`
- `HdfcSavingsParser`
- `AxisSavingsParser`

### AI Fallback Parser

AI fallback should run only when deterministic parsing fails or confidence is low.

AI output must be treated as candidate data and validated before persistence.

---

## 18. Parser Result Model

```python
class TransactionCandidate(BaseModel):
    transaction_date: date
    description: str
    amount: Decimal
    transaction_type: Literal["debit", "credit"]
    institution: str | None = None
    account_type: Literal["credit_card", "savings_account"] | None = None
    account_name: str | None = None
    merchant: str | None = None
    merchant_category: str | None = None
    category: str | None = None
    reference_number: str | None = None
    reward_points: int | None = None
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

## 19. Parse Validation Design

### `parse_validator.py`

Responsibilities:

- Validate required fields
- Validate date format
- Validate amount format
- Validate debit/credit type
- Detect duplicates
- Check whether transaction dates fall within statement period where possible
- Reconcile totals where possible
- Assign confidence level

Confidence levels:

```text
HIGH    → safe to persist
MEDIUM  → persist but flag review_required=true
LOW     → try next parser or AI fallback
FAILED  → mark statement as NEEDS_REVIEW or FAILED
```

---

## 20. Categorization Design

### `categorizer_service.py`

Rule-based categorization for MVP.

| Keywords | Category |
|---|---|
| swiggy, zomato, restaurant, toit | Food |
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

- AI-assisted categorization fallback
- Merchant normalization
- User-defined category rules

---

## 21. AI Service Design

### `ai_service.py`

Responsibilities:

- Support GPT provider integration
- Generate insight explanations
- Support AI parsing fallback through a dedicated parsing prompt
- Handle API failures safely

AI should not be used for final financial calculations.

---

## 22. Repository Layer Design

Repository modules should contain database logic only.

### `transaction_repository.py`

Responsibilities:

- Insert transactions
- Query transactions by user/month
- Aggregate by category
- Aggregate by merchant
- Compare monthly totals

### `statement_repository.py`

Responsibilities:

- Insert statement metadata
- Update ingestion status
- Fetch statement metadata

### `parser_run_repository.py`

Responsibilities:

- Store parser attempts
- Store parser status/confidence/errors
- Support ingestion debugging

---

## 23. Error Handling

| Scenario | Status |
|---|---|
| Missing token | 401 |
| Invalid token | 401 |
| Invalid file type | 400 |
| PDF extraction failed | 422 |
| Parsing failed | 422 |
| Needs manual review | 202 |
| DB unavailable | 503 |
| Unexpected error | 500 |

Rules:

- Return clear API errors.
- Do not expose internal stack traces.
- Log internal errors.
- Fail gracefully for bad PDFs.
- Do not persist low-confidence AI output without validation.

---

## 24. Logging

MVP logging:

- Console logs are sufficient.

Log:

- Request start/end
- File ingestion result
- Parser selected
- Parser confidence
- Number of parsed transactions
- DB errors
- AI fallback errors

Do not log:

- Access tokens
- API keys
- Full sensitive statement content
- Full PDF text extraction output

---

## 25. Security Considerations

- Never commit `.env`
- Never log secrets
- Validate JWT on protected endpoints
- Always filter DB queries by user_id
- Validate uploaded file type
- Restrict upload size
- Use parameterized SQL
- Do not use AI for source-of-truth financial calculations
- Validate AI parsing output before persistence

---

## 26. Analytics Service Design

### `analytics_service.py`

Responsibilities:

- Calculate monthly totals
- Calculate category breakdown
- Calculate income, spend, and net
- Return structured JSON

Important:

- All calculations must be done in SQL or backend code.
- AI must not calculate financial totals.

---

## 27. Comparison Service Design

### `comparison_service.py`

Responsibilities:

- Compare current month vs previous month
- Calculate absolute delta
- Calculate percentage delta
- Handle missing previous data safely

Zero baseline rule:

- If previous amount is 0, percentage delta should be null or marked as not applicable.

---

## 28. Future RAG Design

RAG will be added after structured analytics are stable.

Future components:

- `embedding_service.py`
- `vector_repository.py`
- `rag_service.py`

Rule:

```text
SQL answers numbers.
RAG explains context.
```

---

## 29. Future Frontend Design

Frontend will be developed as a separate application.

Planned screens:

- Login
- Statement upload
- Statement review
- Dashboard
- Monthly summary
- Category breakdown
- Insights
- Natural language query page

---

## 30. Docker Design

Services:

- `app`
- `db`
- `identity-provider`

Data persistence:

- PostgreSQL volume
- Uploaded statement storage volume

App should be configured entirely via environment variables.

---

## 31. AWS Readiness

Future deployment mapping:

| Local Component | AWS Equivalent |
|---|---|
| FastAPI container | ECS / EC2 |
| PostgreSQL | RDS PostgreSQL |
| Local PDF storage | S3 |
| Identity provider | Managed or self-hosted OIDC provider |
| Docker Compose | ECS task definition |

Storage abstraction should be introduced before AWS deployment.

---

## 32. Non-Functional Requirements

### Security

- All user data must be isolated.
- All protected APIs must require authentication.
- Secrets must be managed via environment variables.

### Accuracy

- Financial totals must be deterministic.
- AI must not be used as the source of truth for calculations.
- AI parsing output must be validated.

### Maintainability

- Services should be modular.
- Business logic should not live directly inside API handlers.
- DB queries should be centralized in repositories.
- Bank-specific parsing should be broad and reusable, not card-specific unless unavoidable.

### Extensibility

The design should support:

- Additional banks
- Additional account types
- AI parsing fallback
- AI categorization
- RAG
- Email/SMS ingestion
- Frontend
- AWS deployment

---

## 33. MVP Completion Criteria

MVP is considered complete when:

- Backend runs via Docker
- Authentication is integrated
- PostgreSQL is connected
- PDF statement upload works
- Transactions are parsed and stored
- Parsing failures do not break ingestion silently
- Low-confidence parsing can be flagged for review
- Data is isolated per user
- Monthly summary API works
- AI insights API works
