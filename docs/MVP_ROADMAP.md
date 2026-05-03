# MVP Roadmap — Spend Analyzer

## Product Goal

Build a secure, multi-user, production-style personal finance backend that can ingest financial statements, maintain transaction history, analyze spending, and generate AI-powered insights.

---

## MVP Strategy

The project is divided into multiple MVPs so that each phase delivers usable functionality and builds on the previous phase.

```text
MVP 1 → Foundation
MVP 2 → PDF Ingestion
MVP 3 → Analytics
MVP 4 → AI Intelligence
MVP 5 → Natural Language Query Layer
MVP 6 → RAG and Semantic Search
MVP 7 → Automation
MVP 8 → Frontend
```

---

# MVP 1 — Foundation

## Goal

Set up the core backend platform with Docker, FastAPI, PostgreSQL, and OIDC authentication.

## Outcome

A running backend system with authenticated APIs and user context available.

## Issues

### Issue 1.1 — Project Setup

**Goal:** Initialize repository and base project structure.

**Tasks:**

- Create project folder structure.
- Add `README.md`.
- Add `docs/LLD.md`.
- Add `.gitignore`.
- Add `.env.example`.
- Add base FastAPI app.
- Add `Dockerfile`.
- Add `docker-compose.yml`.
- Add `requirements.txt`.

**Acceptance Criteria:**

- Project runs locally.
- Root API endpoint returns a health response.
- Docker build succeeds.

---

### Issue 1.2 — Configuration Management

**Goal:** Centralize configuration loading.

**Tasks:**

- Create `app/config.py`.
- Load variables from environment.
- Validate required values.
- Avoid hardcoded configuration.

**Acceptance Criteria:**

- App starts when required config exists.
- App fails with clear error when required config is missing.

---

### Issue 1.3 — PostgreSQL Setup

**Goal:** Run PostgreSQL locally through Docker.

**Tasks:**

- Add PostgreSQL service to Docker Compose.
- Configure database using environment variables.
- Add persistent Docker volume.

**Acceptance Criteria:**

- DB container starts.
- Database is reachable from app container.

---

### Issue 1.4 — Database Connection

**Goal:** Connect FastAPI to PostgreSQL.

**Tasks:**

- Create DB connection module.
- Add connection pooling.
- Add `/health/db` endpoint.

**Acceptance Criteria:**

- `/health/db` returns success when DB is reachable.
- Errors are handled cleanly when DB is unavailable.

---

### Issue 1.5 — Authentication Setup

**Goal:** Integrate with OIDC identity provider.

**Tasks:**

- Add identity provider service in Docker Compose.
- Configure realm/client externally.
- Document identity provider setup steps.

**Acceptance Criteria:**

- Identity provider runs locally.
- Access tokens can be generated.

---

### Issue 1.6 — JWT Validation

**Goal:** Protect backend endpoints.

**Tasks:**

- Implement JWT validation dependency.
- Validate token issuer and audience.
- Extract `sub` claim as `user_id`.
- Add `/me` endpoint.

**Acceptance Criteria:**

- Protected endpoint returns 401 without token.
- Protected endpoint works with valid token.
- `user_id` is available to endpoint handlers.

---

# MVP 2 — PDF Ingestion

## Goal

Allow authenticated users to upload PDF statements and convert them into structured transactions.

## Outcome

PDF statements can be uploaded, parsed, categorized, and stored against the authenticated user.

## Issues

### Issue 2.1 — Statement Upload API

**Goal:** Add PDF upload endpoint.

**Endpoint:**

```http
POST /ingest
```

**Tasks:**

- Accept multipart PDF file.
- Validate file type.
- Save file locally.
- Store statement metadata.

**Acceptance Criteria:**

- PDF upload succeeds.
- Non-PDF upload fails with 400.
- Uploaded file has a unique stored filename.

---

### Issue 2.2 — Statement Metadata Table

**Goal:** Store uploaded statement metadata.

**Tasks:**

- Create `statements` table.
- Store user_id, filename, path, account name, statement type, status.

**Acceptance Criteria:**

- Uploaded statement creates a DB record.
- Statement record is linked to authenticated user.

---

### Issue 2.3 — PDF Text/Table Extraction

**Goal:** Extract content from PDF.

**Tasks:**

- Add `pdfplumber`.
- Extract text.
- Extract tables where available.
- Handle invalid PDFs.

**Acceptance Criteria:**

- Extracted content is returned internally.
- Bad PDFs fail gracefully.

---

### Issue 2.4 — Transaction Parser

**Goal:** Convert extracted PDF content into transaction objects.

**Tasks:**

- Parse transaction date.
- Parse description.
- Parse amount.
- Detect debit/credit.

**Acceptance Criteria:**

- Parser returns list of structured transactions.
- Invalid rows are skipped safely.

---

### Issue 2.5 — Rule-Based Categorization

**Goal:** Assign categories to transactions.

**Tasks:**

- Add keyword-based category mapping.
- Add fallback category `Other`.

**Acceptance Criteria:**

- Every parsed transaction has a category.
- Matching is case-insensitive.

---

### Issue 2.6 — Persist Transactions

**Goal:** Save parsed transactions to DB.

**Tasks:**

- Create `transactions` table.
- Insert transactions in batch.
- Link transactions to statement and user.

**Acceptance Criteria:**

- Transactions are stored.
- Transactions are isolated by user_id.
- Insert failures are handled safely.

---

# MVP 3 — Analytics

## Goal

Provide financial summaries and comparisons from stored transactions.

## Outcome

Users can view monthly spend, category breakdown, merchant analysis, and month-on-month comparison.

## Issues

### Issue 3.1 — Monthly Summary API

**Endpoint:**

```http
GET /summary?month=YYYY-MM
```

**Tasks:**

- Calculate total spend.
- Calculate total income.
- Calculate net.
- Group spend by category.

**Acceptance Criteria:**

- Response is user-specific.
- No data month returns empty/zero summary.

---

### Issue 3.2 — Category Breakdown

**Goal:** Show distribution of spending by category.

**Tasks:**

- Return amount and percentage per category.
- Sort by highest spend.

**Acceptance Criteria:**

- Percentages are calculated correctly.
- Categories are sorted descending.

---

### Issue 3.3 — Merchant Analysis

**Goal:** Identify top merchants.

**Tasks:**

- Aggregate spend by merchant.
- Count transactions by merchant.
- Return top N merchants.

**Acceptance Criteria:**

- Results are sorted by spend.
- User isolation is enforced.

---

### Issue 3.4 — Month-on-Month Comparison

**Endpoint:**

```http
GET /comparison?month=YYYY-MM
```

**Tasks:**

- Compare selected month with previous month.
- Calculate total delta.
- Calculate category-wise delta.
- Handle missing previous data.

**Acceptance Criteria:**

- Deltas are calculated correctly.
- Divide-by-zero handled safely.

---

# MVP 4 — AI Intelligence

## Goal

Use AI to provide human-readable financial insights.

## Outcome

Users can get concise insights based on deterministic summaries.

## Issues

### Issue 4.1 — AI Service Setup

**Goal:** Add AI provider integration.

**Tasks:**

- Add AI service module.
- Load AI configuration from environment.
- Add safe error handling.

**Acceptance Criteria:**

- AI service can generate a simple response.
- Missing API key fails clearly.

---

### Issue 4.2 — Insights API

**Endpoint:**

```http
GET /insights?month=YYYY-MM
```

**Tasks:**

- Fetch monthly summary.
- Fetch comparison data if available.
- Build structured prompt.
- Generate insights.

**Acceptance Criteria:**

- AI does not calculate totals.
- Insights are based on provided data only.

---

### Issue 4.3 — AI Categorization Fallback

**Goal:** Improve category coverage.

**Tasks:**

- Use AI only when rule-based category is `Other`.
- Cache merchant/category mapping.

**Acceptance Criteria:**

- Unknown categories reduce over time.
- API failures fall back to `Other`.

---

### Issue 4.4 — Basic Anomaly Detection

**Goal:** Flag unusual transactions.

**Tasks:**

- Identify large spends.
- Identify new merchants.
- Identify category spikes.

**Acceptance Criteria:**

- Anomalies are returned in insights payload.

---

# MVP 5 — Natural Language Query Layer

## Goal

Allow users to ask financial questions in plain English.

## Outcome

User queries are converted into safe structured operations.

## Issues

### Issue 5.1 — Query Endpoint

**Endpoint:**

```http
POST /query
```

**Tasks:**

- Accept natural language query.
- Return structured answer.

**Acceptance Criteria:**

- Endpoint is authenticated.
- Query is user-specific.

---

### Issue 5.2 — Intent Classification

**Goal:** Identify query intent.

**Supported intents:**

- summary
- category
- merchant
- comparison
- insight

**Acceptance Criteria:**

- Queries are classified into supported intents.
- Unknown intent returns helpful fallback.

---

### Issue 5.3 — Safe SQL Mapping

**Goal:** Map intent to safe SQL queries.

**Tasks:**

- Avoid free-form SQL execution initially.
- Use predefined query templates.
- Always include user_id filter.

**Acceptance Criteria:**

- No raw user-generated SQL is executed.
- All results are user-specific.

---

### Issue 5.4 — Response Generation

**Goal:** Convert structured query results into readable answers.

**Tasks:**

- Summarize SQL output.
- Use AI only for wording/explanation.

**Acceptance Criteria:**

- Numbers come from SQL.
- Response is concise and clear.

---

# MVP 6 — RAG and Semantic Search

## Goal

Add semantic retrieval over statements and transaction descriptions.

## Outcome

Users can ask contextual questions that need document-level understanding.

## Issues

### Issue 6.1 — Vector Storage Setup

**Goal:** Add vector search capability.

**Tasks:**

- Enable vector extension or integrate vector DB.
- Create embeddings storage table/collection.

**Acceptance Criteria:**

- Embeddings can be stored and queried.

---

### Issue 6.2 — Statement Chunking

**Goal:** Chunk statement text for retrieval.

**Tasks:**

- Chunk raw statement text.
- Link chunks to source file and user.
- Store metadata.

**Acceptance Criteria:**

- Chunks are tied to user and statement.

---

### Issue 6.3 — Embedding Generation

**Goal:** Generate embeddings for chunks.

**Tasks:**

- Add embedding service.
- Store embeddings.
- Handle AI provider failures.

**Acceptance Criteria:**

- Chunks have embeddings.
- Embeddings are user-isolated.

---

### Issue 6.4 — Retrieval API

**Goal:** Retrieve relevant chunks for a query.

**Tasks:**

- Implement semantic search.
- Return top relevant chunks.
- Filter by user_id.

**Acceptance Criteria:**

- Retrieval returns relevant context.
- User isolation is enforced.

---

### Issue 6.5 — RAG Query Pipeline

**Goal:** Combine SQL + retrieval + AI answer.

**Tasks:**

- Retrieve structured data where needed.
- Retrieve text chunks where needed.
- Generate grounded answer.

**Acceptance Criteria:**

- Answers cite or reference retrieved context internally.
- Financial numbers come from SQL.

---

# MVP 7 — Automation

## Goal

Reduce manual statement uploads.

## Issues

### Issue 7.1 — Email Ingestion

- Connect to mailbox.
- Identify statement emails.
- Download attachments.
- Trigger ingestion.

### Issue 7.2 — SMS Parsing

- Define SMS ingestion format.
- Parse transaction SMS.
- Store transaction records.

### Issue 7.3 — Scheduled Jobs

- Add scheduler.
- Run ingestion periodically.
- Track job status.

### Issue 7.4 — Recurring Payment Detection

- Detect repeated monthly merchants.
- Identify subscriptions and EMIs.

### Issue 7.5 — Budget Alerts

- Configure category budgets.
- Notify when spend crosses threshold.

---

# MVP 8 — Frontend

## Goal

Create a usable web interface for authenticated users.

## Issues

### Issue 8.1 — Frontend Setup

- Create React/Vite app.
- Configure routing.
- Add environment-based API URL.

### Issue 8.2 — Auth Integration

- Integrate OIDC login.
- Store access token securely.
- Attach token to API requests.

### Issue 8.3 — Statement Upload Page

- Upload PDF.
- Show ingestion status.

### Issue 8.4 — Dashboard

- Display monthly summary.
- Display category breakdown.
- Display top merchants.

### Issue 8.5 — Insights Page

- Show AI insights.
- Show anomalies.

### Issue 8.6 — Query Page

- Natural language query input.
- Display answer.

---

## Priority Recommendation

Build in this order:

```text
MVP 1 → MVP 2 → MVP 3 → MVP 4 → MVP 5 → MVP 6 → MVP 8 → MVP 7
```

Reason:

- Foundation first
- Ingestion before analytics
- Analytics before AI
- Structured query before RAG
- Frontend after core APIs are stable
- Automation after data model matures

---

## Definition of Done for Entire Product

The complete product is considered mature when:

- Multiple users can authenticate securely.
- Each user can ingest statements.
- Transactions are accurately stored and isolated.
- Users can analyze monthly and historical spend.
- Users can ask natural language questions.
- AI provides grounded insights.
- Frontend provides a usable dashboard.
- System can be deployed to cloud infrastructure.
