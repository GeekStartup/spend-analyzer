# Low-Level Design (LLD) — Spend Analyzer

## 1. Purpose

This document describes the low-level design for **Spend Analyzer**, a secure, multi-user personal finance backend system.

The system ingests bank and credit card statements, extracts transactions, stores them securely, and provides financial analytics and AI-powered insights.

---

## 2. Scope

This LLD focuses on the backend design for the following capabilities:

- User authentication using OAuth2 / OIDC
- User-level data isolation
- PDF statement ingestion
- Transaction extraction and normalization
- PostgreSQL persistence
- Monthly and category-wise analytics
- AI-generated insights
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
- Use AI only for explanation, insight, categorization fallback, and future query intelligence.
- Keep PDF parsing deterministic for MVP.
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
| AI Provider | OpenAI API |
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
│   ├── db/
│   ├── models/
│   ├── services/
│   └── utils/
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
OIDC_ISSUER_URL
OIDC_JWKS_URL
OIDC_AUDIENCE
OIDC_REALM
OIDC_CLIENT_ID
```

#### AI

```text
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

## 9. Request Authentication Flow

```text
Client
  |
  | 1. Login via Identity Provider
  v
Identity Provider
  |
  | 2. Access token issued
  v
Client
  |
  | 3. Authorization: Bearer <token>
  v
FastAPI Backend
  |
  | 4. Validate token
  | 5. Extract user_id
  v
Protected endpoint
```

---

## 10. API Layer Design

| Module | Responsibility |
|---|---|
| `health.py` | Health checks |
| `ingestion.py` | PDF upload and ingestion |
| `transactions.py` | Transaction listing/filtering |
| `summary.py` | Monthly summary APIs |
| `comparison.py` | Month-on-month comparison |
| `insights.py` | AI-generated insights |

---

## 11. API Endpoints

### Health

```http
GET /
```

Response:

```json
{
  "status": "ok",
  "service": "spend-analyzer"
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
- `account_name`: optional
- `statement_type`: optional, e.g. `credit_card`, `bank_account`

Response:

```json
{
  "status": "success",
  "source_file_id": "uuid",
  "transactions_ingested": 42
}
```

### Monthly Summary

```http
GET /summary?month=YYYY-MM
Authorization: Bearer <token>
```

Response:

```json
{
  "month": "2026-04",
  "total_spend": 45000,
  "total_income": 50000,
  "net": 5000,
  "categories": [
    {
      "category": "Food",
      "amount": 12000,
      "percentage": 26.67
    }
  ]
}
```

### Month-on-Month Comparison

```http
GET /comparison?month=YYYY-MM
Authorization: Bearer <token>
```

Response:

```json
{
  "current_month": "2026-04",
  "previous_month": "2026-03",
  "total_spend_delta": 4200,
  "category_deltas": [
    {
      "category": "Food",
      "current": 12000,
      "previous": 8500,
      "delta": 3500,
      "delta_percentage": 41.18
    }
  ]
}
```

### AI Insights

```http
GET /insights?month=YYYY-MM
Authorization: Bearer <token>
```

Response:

```json
{
  "month": "2026-04",
  "insights": [
    "Food spending increased significantly compared to the previous month.",
    "Shopping includes multiple high-value transactions."
  ]
}
```

---

## 12. Data Model

### Table: `statements`

Stores uploaded statement metadata.

```sql
CREATE TABLE statements (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_name TEXT,
    statement_type TEXT,
    original_file_name TEXT NOT NULL,
    stored_file_path TEXT NOT NULL,
    status TEXT NOT NULL,
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
    category TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    transaction_type TEXT NOT NULL,
    account_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
Extract PDF content
   |
   v
Parse transactions
   |
   v
Categorize transactions
   |
   v
Insert transactions
   |
   v
Return ingestion result
```

---

## 15. PDF Extraction Design

### `pdf_service.py`

Responsibilities:

- Open PDF file
- Extract text
- Extract tables where available
- Return raw extracted content

MVP approach:

- Use deterministic extraction
- Do not use AI for PDF parsing
- Log extraction failures gracefully

---

## 16. Transaction Parser Design

### `parser_service.py`

Responsibilities:

- Convert raw PDF content into transaction candidates
- Extract transaction date, description, amount, and debit/credit type

Parser output:

```python
[
    {
        "transaction_date": "2026-04-01",
        "description": "SWIGGY ORDER",
        "amount": -450.00,
        "transaction_type": "debit"
    }
]
```

MVP parser can be heuristic-based.

Future:

- Bank-specific parsers
- Template-based parsing
- AI fallback for messy formats

---

## 17. Categorization Design

### `categorizer_service.py`

Rule-based categorization for MVP.

| Keywords | Category |
|---|---|
| swiggy, zomato, restaurant | Food |
| uber, ola, fuel | Travel |
| amazon, flipkart | Shopping |
| rent | Housing |
| emi, loan | EMI |
| netflix, spotify | Subscriptions |
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

## 18. Analytics Service Design

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

## 19. Comparison Service Design

### `comparison_service.py`

Responsibilities:

- Compare current month vs previous month
- Calculate absolute delta
- Calculate percentage delta
- Handle missing previous data safely

Zero baseline rule:

- If previous amount is 0, percentage delta should be null or marked as not applicable.

---

## 20. AI Service Design

### `ai_service.py`

Responsibilities:

- Generate insights from structured summaries
- Explain trends
- Provide recommendations

Input to AI should be structured summary, not raw private financial PDFs unless required.

---

## 21. Repository Layer Design

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

---

## 22. Error Handling

| Scenario | Status |
|---|---|
| Missing token | 401 |
| Invalid token | 401 |
| Invalid file type | 400 |
| PDF extraction failed | 422 |
| DB unavailable | 503 |
| Unexpected error | 500 |

Rules:

- Return clear API errors.
- Do not expose internal stack traces.
- Log internal errors.
- Fail gracefully for bad PDFs.

---

## 23. Logging

MVP logging:

- Console logs are sufficient.

Log:

- Request start/end
- File ingestion result
- Number of parsed transactions
- DB errors
- AI errors

Do not log:

- Access tokens
- API keys
- Full sensitive statement content

---

## 24. Security Considerations

- Never commit `.env`
- Never log secrets
- Validate JWT on protected endpoints
- Always filter DB queries by user_id
- Validate uploaded file type
- Restrict upload size
- Use parameterized SQL
- Do not use AI for source-of-truth financial calculations

---

## 25. Future RAG Design

RAG will be added after structured analytics are stable.

Future components:

- `embedding_service.py`
- `vector_repository.py`
- `rag_service.py`

Possible flow:

```text
Statement text / transaction descriptions
   |
   v
Chunk
   |
   v
Embed
   |
   v
Store in vector DB
   |
   v
Retrieve relevant context
   |
   v
Combine with SQL results
   |
   v
Generate grounded answer
```

Rule:

```text
SQL answers numbers.
RAG explains context.
```

---

## 26. Future Frontend Design

Frontend will be developed as a separate application.

Planned screens:

- Login
- Statement upload
- Dashboard
- Monthly summary
- Category breakdown
- Insights
- Natural language query page

---

## 27. Docker Design

Services:

- `app`
- `db`
- `identity-provider`

Data persistence:

- PostgreSQL volume
- Uploaded statement storage volume

App should be configured entirely via environment variables.

---

## 28. AWS Readiness

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

## 29. Non-Functional Requirements

### Security

- All user data must be isolated.
- All protected APIs must require authentication.
- Secrets must be managed via environment variables.

### Accuracy

- Financial totals must be deterministic.
- AI must not be used as the source of truth for calculations.

### Maintainability

- Services should be modular.
- Business logic should not live directly inside API handlers.
- DB queries should be centralized in repositories.

### Extensibility

The design should support:

- Additional banks
- Additional users
- AI categorization
- RAG
- Email/SMS ingestion
- Frontend
- AWS deployment

---

## 30. MVP Completion Criteria

MVP is considered complete when:

- Backend runs via Docker
- Authentication is integrated
- PostgreSQL is connected
- PDF statement upload works
- Transactions are parsed and stored
- Data is isolated per user
- Monthly summary API works
- AI insights API works
