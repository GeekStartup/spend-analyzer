# Learning Guide — Spend Analyzer

## 1. Purpose

Spend Analyzer is intentionally designed as both:

1. a production-style personal finance backend, and
2. a structured learning project for Python, backend engineering, AI, RAG, and controlled agentic workflows.

The project should not be optimized only for fastest feature delivery. Each task should teach an important engineering concept while still moving the product forward.

Core principle:

```text
Backend validates and calculates.
AI assists, explains, routes, and retrieves.
```

---

## 2. Learning Objectives

### Python and Backend Engineering

The project should teach practical Python through real backend modules, not isolated syntax exercises.

Learning goals:

- Python package structure
- Type hints
- Pydantic models
- Dependency management
- FastAPI routing and dependencies
- Service and repository layering
- File handling
- Error handling
- Unit and integration testing with pytest
- PostgreSQL-backed data modelling
- Clean code, refactoring, and quality gates

### AI Engineering

AI should be introduced through controlled backend patterns.

Learning goals:

- AI provider abstraction
- Prompt builder design
- Structured outputs
- Pydantic validation of AI responses
- AI fallback logic
- Confidence scoring
- Guardrails
- Cost-aware AI usage
- Mocking AI clients in tests
- Evaluation datasets for regression checks

### RAG Pipeline

RAG should be added after ingestion and deterministic analytics are reliable.

Learning goals:

- Chunking
- Embeddings
- Vector storage
- Similarity retrieval
- Context assembly
- User-isolated retrieval
- Hybrid SQL + RAG answering
- Retrieval evaluation

### Controlled Agentic AI

Agentic workflows should come after deterministic APIs, query routing, and RAG are stable.

Learning goals:

- Tool registry design
- Tool selection
- Planning vs execution separation
- Agent state
- Safe tool invocation
- Multi-step reasoning over user financial data
- Guardrails against unsafe SQL or unsupported actions
- Agent execution tracing

---

## 3. Architecture for Learning

The codebase should be organized around clear responsibilities.

```text
Client / API Caller
  ↓
FastAPI Routes
  ↓
Application Services
  ↓
Repositories / External Providers
  ↓
PostgreSQL / File Storage / AI Provider
```

AI-specific architecture:

```text
User Query / Ingestion Failure
  ↓
AI Orchestration Layer
  ↓
Prompt Builder / Tool Router / Retrieval Service
  ↓
AI Provider / SQL-backed Tools / Vector Store
  ↓
Validated Response
```

Recommended package direction as the project matures:

```text
app/
├── api/
├── auth/
├── core/
├── db/
├── models/
├── schemas/
├── repositories/
├── services/
├── parsing/
├── ai/
├── rag/
└── agents/
```

---

## 4. Python Concepts Mapped to Modules

| Python Concept | Where It Is Learned |
|---|---|
| Type hints | Schemas, services, parsers |
| Pydantic models | API contracts, parser outputs, AI structured outputs |
| File handling | PDF upload and extraction |
| Exceptions | Core errors, parsing failures, AI failures |
| Dependency injection | FastAPI dependencies and service wiring |
| Database access | Repository layer |
| Testing | Parser tests, service tests, API tests |
| Package design | Separation of API, services, repositories, AI, RAG, and agents |
| Security validation | Auth dependencies, JWT validation, upload validation |
| Quality gates | Ruff, Bandit, pip-audit, coverage checks |

---

## 5. Deterministic Backend Rules

Deterministic backend logic owns:

- Authentication
- User isolation
- File validation
- PDF extraction orchestration
- Transaction validation
- Transaction persistence
- Analytics calculations
- SQL query execution
- Data access control

AI must not own these responsibilities.

Disallowed AI use cases:

- Final financial total calculation
- Raw SQL generation and execution
- Persisting unvalidated financial records
- Cross-user data access

---

## 6. Parsing Learning Path

Parsing should follow `docs/PARSING_STRATEGY.md`.

Core flow:

```text
PDF Extractor
  ↓
Statement Detector
  ↓
Generic Parser
  ↓
Broad Bank/Account Parser
  ↓
AI Fallback Parser
  ↓
Parse Validator
  ↓
Persist or Needs Review
```

Learning goals:

- Regex and text processing
- Pydantic modelling
- Decimal handling for money
- Confidence scoring
- Defensive parsing
- Validation before persistence
- AI structured output validation

---

## 7. RAG Design Rules

RAG answers must remain grounded.

Rules:

- Every chunk must include `user_id`.
- Retrieval must filter by `user_id`.
- Retrieved text explains context; SQL provides numbers.
- RAG answers must not invent totals.
- If retrieval is weak, return a clear fallback.

Preferred hybrid pattern:

```text
Question: Why was my food spend high in March?

SQL:
- Calculate March food spend
- Compare with previous month
- Identify top food merchants

RAG:
- Retrieve statement snippets or transaction descriptions that explain context

AI:
- Generate explanation from SQL facts + retrieved context
```

---

## 8. Agentic AI Rules

The agent must not directly access the database.

It can only call predefined backend tools.

Example tools:

```text
get_monthly_summary(user_id, month)
get_category_breakdown(user_id, month)
get_top_merchants(user_id, month)
compare_months(user_id, month)
retrieve_statement_context(user_id, query)
generate_insight(summary, comparison, context)
```

Guardrails:

- Agent can only use registered tools.
- Tools must enforce `user_id` internally.
- No arbitrary SQL tool in early versions.
- Unsupported intents should return a fallback.
- Agent steps should be logged for debugging.
- Financial values must come from tools, not model reasoning.

---

## 9. Learning Phase Plan

### Phase 1 — Python + FastAPI Foundation

Goal: build the base backend and learn Python web service fundamentals.

Learning objectives:

- Python package structure
- FastAPI app setup
- Routing
- Environment configuration
- Docker basics
- Health checks
- Basic testing

Related issues:

- #1 Project setup
- #2 Centralized configuration management
- #3 PostgreSQL connectivity
- #4 Initial database schema
- #5 OIDC identity provider setup
- #6 JWT validation and authenticated user context

### Phase 2 — PostgreSQL + Repository Pattern

Goal: learn database-backed backend design.

Learning objectives:

- SQL table design
- Indexing
- Repository pattern
- Parameterized queries
- Transaction management
- User-level data isolation

Related issues:

- #4 Initial database schema
- #8 Store uploaded statement metadata
- #12 Persist parsed transactions with user isolation

### Phase 3 — PDF Ingestion and Parsing

Goal: learn file ingestion, PDF extraction, parser modelling, validation, and defensive Python.

Learning objectives:

- Multipart upload handling
- File validation
- PDF text/table extraction
- Pydantic parser models
- Regex/text parsing
- Decimal handling for money
- Parser run auditability

Related issues:

- #7 Statement upload API
- #8 Store uploaded statement metadata
- #9 Extract text and tables from PDF statements
- #10 Resilient transaction parsing pipeline
- #11 Rule-based transaction categorization
- #12 Persist parsed transactions with user isolation
- #42 AI parsing fallback

### Phase 4 — Deterministic Analytics

Goal: learn backend analytics using SQL and service-layer calculations.

Learning objectives:

- Aggregation queries
- Date filtering
- Month handling
- Percentages and divide-by-zero safety
- API response schemas
- Separation of SQL facts from AI wording

Related issues:

- #13 Monthly summary API
- #14 Category breakdown API
- #15 Merchant analysis API
- #16 Month-on-month comparison API
- #20 Basic anomaly detection

### Phase 5 — AI Service and Structured Output

Goal: learn safe AI integration through a provider abstraction and strict structured output validation.

Learning objectives:

- AI provider abstraction
- Prompt builder design
- Structured JSON outputs
- Pydantic validation of AI responses
- Mocking AI clients in tests
- Cost-aware fallback usage
- Failure handling

Related issues:

- #17 AI service setup
- #18 AI insights API
- #19 AI categorization fallback
- #42 AI parsing fallback

### Phase 6 — Natural Language Query Routing

Goal: safely convert user questions into backend operations.

Learning objectives:

- Intent classification
- Safe query routing
- Tool/function mapping
- Parameter extraction
- Guardrails against raw SQL
- Response generation from trusted facts

Related issues:

- #21 Natural language query endpoint
- #22 Query intent classification
- #23 Safe SQL templates
- #24 Readable answer generation

### Phase 7 — RAG Pipeline

Goal: learn retrieval-augmented generation over user-owned statement context.

Learning objectives:

- Chunking
- Embeddings
- Vector storage
- Similarity search
- Retrieval filtering by user
- Context assembly
- Hybrid SQL + RAG answering
- Retrieval evaluation

Related issues:

- #25 Vector storage
- #26 Chunk statement text and transaction descriptions
- #27 Generate and persist embeddings
- #28 Semantic retrieval API/service
- #29 RAG query pipeline

### Phase 8 — Controlled Finance Agent

Goal: learn agentic AI safely using predefined backend tools.

Learning objectives:

- Agent planning
- Tool registry
- Tool invocation
- Agent state
- Guardrails
- Audit logs
- Multi-step query execution
- Limiting autonomy in financial systems

### Phase 9 — Frontend

Goal: build a usable interface after core backend and AI flows are stable.

Learning objectives:

- React/Vite basics
- API integration
- OIDC token usage
- Upload UI
- Dashboard UI
- AI insight UI

### Phase 10 — Automation

Goal: explore automated data ingestion after the core system is reliable.

Learning objectives:

- Scheduled jobs
- Email parsing
- SMS parsing
- Duplicate detection
- Background processing

---

## 10. Issue Quality Checklist

Every issue should ideally include:

- Goal
- Learning objectives
- Tasks
- Acceptance criteria
- Test expectations
- Safety/security notes where applicable

---

## 11. Definition of Learning Done

A phase is complete only when:

- The feature works.
- Tests exist.
- The code is understandable.
- The design decision is documented.
- The learning objective is clear.
- The implementation avoids shortcuts that hide important concepts.
