# Learning Task Plan — Spend Analyzer

## Purpose

This document converts the project into a structured learning roadmap. GitHub issues are the executable task list.

The project should be built in small increments, with each issue teaching a concrete Python, backend, AI, RAG, or agentic AI concept.

---

## Phase 1 — Python + FastAPI Foundation

### Goal
Build the base backend structure and learn Python web service fundamentals.

### Learning Objectives

- Python package structure
- FastAPI app setup
- Routing
- Environment configuration
- Docker basics
- Health checks
- Basic testing

### Existing Issues

- #1 Project setup with FastAPI, Docker, PostgreSQL and OIDC provider
- #2 Centralized configuration management
- #3 PostgreSQL service and database connectivity
- #4 Initial database schema
- #5 OIDC identity provider setup
- #6 JWT validation and authenticated user context

### Required Enhancements

Each issue should include test expectations and explicit Python learning objectives where missing.

---

## Phase 2 — PostgreSQL + Repository Pattern

### Goal
Learn database-backed backend design using repositories and service layers.

### Learning Objectives

- SQL table design
- Indexing
- Repository pattern
- Parameterized queries
- Transaction management
- User-level data isolation

### Existing Issues

- #4 Initial database schema
- #8 Store uploaded statement metadata
- #12 Persist parsed transactions with user isolation

### Required Enhancements

- Add migration strategy.
- Add repository test expectations.
- Add sample seed/test data strategy.

---

## Phase 3 — PDF Ingestion and Parsing

### Goal
Learn file ingestion, PDF extraction, parser modelling, validation, and defensive Python.

### Learning Objectives

- Multipart upload handling
- File validation
- PDF text/table extraction
- Pydantic parser models
- Regex/text parsing
- Decimal handling for money
- Validation and confidence scoring
- Parser run auditability

### Existing Issues

- #7 Statement upload API
- #8 Store uploaded statement metadata
- #9 Extract text and tables from PDF statements
- #10 Resilient transaction parsing pipeline
- #11 Rule-based transaction categorization
- #12 Persist parsed transactions with user isolation
- #42 AI parsing fallback

### Required Enhancements

- Add sample statement fixtures.
- Add parser unit tests.
- Add AI output contract tests.
- Keep parser design broad, not card-specific.

---

## Phase 4 — Deterministic Analytics

### Goal
Learn backend analytics using SQL and service-layer calculations.

### Learning Objectives

- Aggregation queries
- Date filtering
- Month handling
- Percentages and divide-by-zero safety
- API response schemas
- Separation of SQL facts from AI wording

### Existing Issues

- #13 Monthly summary API
- #14 Category breakdown API
- #15 Merchant analysis API
- #16 Month-on-month comparison API
- #20 Basic anomaly detection

### Required Enhancements

- Add deterministic test data.
- Add tests for zero and empty data cases.
- Ensure all queries filter by `user_id`.

---

## Phase 5 — AI Service and Structured Output

### Goal
Learn safe AI integration through a provider abstraction and strict structured output validation.

### Learning Objectives

- AI provider abstraction
- Prompt builder design
- Structured JSON outputs
- Pydantic validation of AI responses
- Mocking AI clients in tests
- Cost-aware fallback usage
- Failure handling

### Existing Issues

- #17 AI service setup
- #18 AI insights API
- #19 AI categorization fallback
- #42 AI parsing fallback

### New Issues Recommended

- AI client abstraction and mock client
- Structured output validation utilities
- AI prompt templates and fixtures
- AI evaluation dataset for parser fallback

---

## Phase 6 — Natural Language Query Routing

### Goal
Learn how to safely convert user questions into backend operations.

### Learning Objectives

- Intent classification
- Safe query routing
- Tool/function mapping
- Parameter extraction
- Guardrails against raw SQL
- Response generation from trusted facts

### Existing Issues

- #21 Natural language query endpoint
- #22 Query intent classification
- #23 Safe SQL templates
- #24 Readable answer generation

### Required Enhancements

- Add examples of supported queries.
- Add unsupported query fallback.
- Add tests proving raw SQL is never executed.

---

## Phase 7 — RAG Pipeline

### Goal
Learn retrieval-augmented generation over user-owned statement context.

### Learning Objectives

- Chunking
- Embeddings
- Vector storage
- Similarity search
- Retrieval filtering by user
- Context assembly
- Hybrid SQL + RAG answering
- Retrieval evaluation

### Existing Issues

- #25 Vector storage
- #26 Chunk statement text and transaction descriptions
- #27 Generate and persist embeddings
- #28 Semantic retrieval API/service
- #29 RAG query pipeline

### New Issues Recommended

- RAG evaluation fixtures
- Context builder and prompt assembly
- Hybrid SQL + RAG answer contract

---

## Phase 8 — Controlled Finance Agent

### Goal
Learn agentic AI safely using predefined backend tools.

### Learning Objectives

- Agent planning
- Tool registry
- Tool invocation
- Agent state
- Guardrails
- Audit logs
- Multi-step query execution
- Limiting autonomy in financial systems

### New Issues Recommended

- Create finance agent tool registry
- Implement read-only finance tools
- Implement agent planner
- Add agent execution trace logging
- Add agent guardrail tests
- Add multi-step finance query examples

### Agent Boundary Rule

The agent must not directly execute SQL or access database repositories. It should call safe service-layer tools only.

---

## Phase 9 — Frontend

### Goal
Build a usable interface after core backend and AI flows are stable.

### Learning Objectives

- React/Vite basics
- API integration
- OIDC token usage
- Upload UI
- Dashboard UI
- AI insight UI

### Existing Issues

- #35 Frontend setup
- #36 Frontend OIDC login
- #37 Statement upload page
- #38 Dashboard and monthly summary view
- #39 AI insights page
- #40 Natural language query page

---

## Phase 10 — Automation

### Goal
Explore automated data ingestion after the core system is reliable.

### Learning Objectives

- Scheduled jobs
- Email parsing
- SMS parsing
- Duplicate detection
- Background processing

### Existing Issues

- #30 Email ingestion
- #31 SMS transaction parsing
- #32 Scheduled ingestion jobs
- #33 Recurring payments and subscriptions
- #34 Budget alerts

---

## Recommended Next Issues To Work On

For the current learning path, prioritize:

1. #2 Configuration management
2. #3 PostgreSQL connectivity
3. #4 Database schema
4. #6 JWT validation
5. #7 Statement upload API
6. #9 PDF extraction
7. #10 Parsing pipeline
8. AI client abstraction issue
9. Structured output validation issue
10. #42 AI fallback parsing

---

## Issue Quality Checklist

Every new issue should ideally include:

- Goal
- Learning objectives
- Tasks
- Acceptance criteria
- Test expectations
- Safety/security notes where applicable

---

## Definition of Learning Done

A phase is complete only when:

- The feature works
- Tests exist
- The code is understandable
- The design decision is documented
- The learning objective is clear
- The implementation avoids shortcuts that would hide important concepts
