# Learning-First Design — Spend Analyzer

## 1. Design Objective

Spend Analyzer is designed to be both a useful personal finance backend and a structured learning project for Python and AI engineering.

The design deliberately separates deterministic backend logic from AI-assisted logic so that the project teaches correct production patterns:

```text
Backend validates and calculates.
AI assists, explains, routes, and retrieves.
```

---

## 2. Architecture Overview

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

---

## 3. Python Learning Design

The Python codebase should be built around clear module responsibilities.

### 3.1 Recommended Package Structure

```text
app/
├── main.py
├── config.py
├── api/
│   ├── health_routes.py
│   ├── ingestion_routes.py
│   ├── transaction_routes.py
│   ├── analytics_routes.py
│   ├── insight_routes.py
│   └── query_routes.py
├── auth/
│   ├── jwt_validator.py
│   └── dependencies.py
├── core/
│   ├── errors.py
│   ├── logging.py
│   └── constants.py
├── db/
│   ├── connection.py
│   └── migrations/
├── models/
│   └── db_models.py
├── schemas/
│   ├── statement_schema.py
│   ├── transaction_schema.py
│   ├── analytics_schema.py
│   └── query_schema.py
├── repositories/
│   ├── statement_repository.py
│   ├── transaction_repository.py
│   ├── parser_run_repository.py
│   └── vector_repository.py
├── services/
│   ├── ingestion_service.py
│   ├── analytics_service.py
│   ├── categorizer_service.py
│   ├── insight_service.py
│   └── query_service.py
├── parsing/
│   ├── models.py
│   ├── pdf_extractor.py
│   ├── statement_detector.py
│   ├── generic_parser.py
│   ├── parse_validator.py
│   ├── ai_fallback_parser.py
│   └── bank_parsers/
├── ai/
│   ├── ai_client.py
│   ├── prompt_builder.py
│   ├── structured_output.py
│   ├── ai_guardrails.py
│   └── evaluation.py
├── rag/
│   ├── chunker.py
│   ├── embedding_service.py
│   ├── retrieval_service.py
│   ├── context_builder.py
│   └── rag_service.py
└── agents/
    ├── finance_agent.py
    ├── tool_registry.py
    ├── tools.py
    └── planner.py
```

### 3.2 Python Concepts Mapped to Modules

| Python Concept | Where It Is Learned |
|---|---|
| Type hints | Schemas, services, parsers |
| Pydantic models | API contracts, parser outputs, AI structured outputs |
| File handling | PDF upload and extraction |
| Exceptions | `core/errors.py`, parsing failures, AI failures |
| Dependency injection | FastAPI dependencies and service wiring |
| Database access | Repository layer |
| Testing | Parser tests, service tests, API tests |
| Package design | Separation of `api`, `services`, `repositories`, `ai`, `rag`, `agents` |

---

## 4. Deterministic Backend Design

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

AI does not own these responsibilities.

---

## 5. AI Design

### 5.1 AI Provider Abstraction

AI access should go through a dedicated client abstraction:

```text
AIClient
  ├── generate_text()
  ├── generate_structured_output()
  └── generate_embedding()
```

Benefits:

- Easy to switch providers later
- Centralized retries/timeouts
- Centralized logging and redaction
- Easier testing with mocks

### 5.2 AI Use Cases

Allowed AI use cases:

- Parsing fallback
- Categorization fallback
- Insight wording
- Intent classification
- Query response explanation
- RAG answer generation
- Agent planning over predefined tools

Disallowed AI use cases:

- Final financial total calculation
- Raw SQL generation and execution
- Persisting unvalidated financial records
- Cross-user data access

---

## 6. Parsing Design

Parsing should follow the dedicated parsing strategy in `docs/PARSING_STRATEGY.md`.

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
- Confidence scoring
- Defensive parsing
- Validation before persistence
- AI structured output validation

---

## 7. RAG Design

RAG should be introduced only after transactions and analytics are reliable.

### 7.1 RAG Components

```text
Raw statement text / transaction text
  ↓
Chunker
  ↓
Embedding Service
  ↓
Vector Repository
  ↓
Retrieval Service
  ↓
Context Builder
  ↓
RAG Service
  ↓
Grounded Answer
```

### 7.2 RAG Rules

- Every chunk must include `user_id`.
- Retrieval must filter by `user_id`.
- Retrieved text explains context; SQL provides numbers.
- RAG answers must not invent totals.
- If retrieval is weak, return a clear fallback.

### 7.3 Hybrid SQL + RAG Pattern

For finance questions, the preferred design is hybrid:

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

## 8. Agentic AI Design

Agentic workflows should be added after query APIs and RAG are available.

### 8.1 Agent Boundary

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

### 8.2 Agent Flow

```text
User question
  ↓
Planner
  ↓
Tool selection
  ↓
Tool execution
  ↓
Observation aggregation
  ↓
Final response generation
  ↓
Validation / guardrails
```

### 8.3 Agent Guardrails

- Agent can only use registered tools.
- Tools must enforce `user_id` internally.
- No arbitrary SQL tool in early versions.
- Unsupported intents should return a fallback.
- Agent steps should be logged for debugging.
- Financial values must come from tools, not model reasoning.

---

## 9. Testing Design

Testing is part of the learning objective, not optional.

### 9.1 Test Types

| Test Type | Purpose |
|---|---|
| Unit tests | Test pure Python functions and parsers |
| Service tests | Test business logic with mocked repositories |
| Repository tests | Test SQL/database behavior |
| API tests | Test FastAPI endpoints |
| AI contract tests | Test structured AI output validation with fixtures |
| RAG tests | Test chunking, retrieval, and context building |
| Agent tests | Test tool routing and guardrails |

### 9.2 Test Philosophy

- Deterministic logic should have deterministic tests.
- AI behavior should be tested through contracts and fixtures.
- Do not require live AI calls for normal unit tests.
- Use mock AI clients in tests.

---

## 10. Task Design Rules

GitHub issues should include learning objectives.

Each issue should ideally contain:

- Goal
- Learning objectives
- Tasks
- Acceptance criteria
- Test expectations

Example:

```text
## Learning Objectives
- Learn Pydantic models
- Learn Python Decimal usage
- Learn validation before persistence
```

---

## 11. Recommended Build Order

Learning-first order:

```text
Phase 1: Python + FastAPI foundation
Phase 2: PostgreSQL + repository pattern
Phase 3: PDF ingestion and parsing
Phase 4: Analytics with SQL/backend logic
Phase 5: AI service + structured output
Phase 6: AI fallback parsing and categorization
Phase 7: Natural language query routing
Phase 8: RAG pipeline
Phase 9: Controlled finance agent
Phase 10: Frontend and automation
```

This differs slightly from a pure product roadmap because it prioritizes learning foundations before advanced AI features.
