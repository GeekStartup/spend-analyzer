# AI Engineering Assistant Operating Contract

This file is the mandatory entry point for any AI engineering assistant working on Spend Analyzer.

Before proposing, reviewing, or changing repository content, read **all of `AGENTS_CORE.md`**. `AGENTS_CORE.md` preserves the complete original operating contract. The refinements below supplement that contract. If wording conflicts, this file takes precedence.

---

## Refinements after the observability foundation

### 1. Tool-driven commits and branch history

When direct tooling requires temporary or incremental commits:

- disclose the limitation as soon as it is known;
- do not claim the history is clean until it has been verified;
- remove temporary files from the final tree;
- do not rewrite or force-push a shared branch without explicit approval;
- otherwise report the commit history accurately and rely on squash merge where appropriate.

### 2. Feature-level telemetry decisions

For every meaningful application flow, explicitly choose one or more of:

- baseline HTTP telemetry only;
- structured business-event log;
- bounded metric;
- manual span;
- no additional telemetry, with justification.

Do not instrument every function. Add custom telemetry around meaningful business outcomes and dependency boundaries.

### 3. Safe exception telemetry

Raw exception messages and stack traces are uncontrolled data. They may contain credentials, file paths, financial content, SQL, bind values, or third-party payloads.

Therefore:

- do not log or record raw exception messages or stack traces by default;
- use bounded failure categories;
- record exception class names through the shared safe helpers;
- for sensitive manual spans, disable automatic exception recording and automatic exception-derived status where necessary;
- set sanitized events, attributes, and span status explicitly.

### 4. Health probes and self-observation

- Do not emit a success business log for every health probe.
- Emit safe failure telemetry for unhealthy dependencies.
- Exclude the metrics endpoint from request logs, HTTP metrics, and traces.
- Avoid telemetry loops, scrape noise, and duplicate request-start/request-completion logs when one outcome-summary event is sufficient.

### 5. Optional observability infrastructure

The application must remain functional without Prometheus, Grafana, Tempo, OpenTelemetry Collector, or PostgreSQL exporter.

Optional observability services belong in the normal Docker Compose `observability` profile.

Do not duplicate those services into `docker-compose.test.yml` unless a test directly requires the complete telemetry stack.

Use a dedicated smoke/integration workflow when automated end-to-end observability verification is justified. Grafana data sources, trace visualization, PromQL queries, and operational workflows may require manual validation.

Whenever Compose files or mounted service configuration change, validate all supported configurations:

```powershell
docker compose config --quiet
docker compose --profile observability config --quiet
docker compose -f docker-compose.test.yml config --quiet
```

### 6. Observability documentation ownership

Keep documentation responsibilities distinct:

- `AGENTS.md` and `AGENTS_CORE.md`: repository-wide assistant and engineering rules;
- `docs/HLD.md`: architecture and signal topology;
- `docs/OBSERVABILITY_LLD.md`: implementation-level logging, metrics, tracing, and correlation design;
- `docs/LOCAL_OBSERVABILITY.md`: startup, inspection, debugging, and operational procedures.

Avoid duplicating the same detailed content across these documents.

### 7. Correct parsing order

The preferred parsing order is:

```text
Generic deterministic parser
→ broad bank/account parser
→ AI fallback
→ backend validation
→ candidate persistence
→ reconciliation or manual review
```

Do not create a parser for every card product unless evidence shows that a broad parser cannot support the format.

AI fallback must not silently override deterministic results.

### 8. Repository context and documentation reading map

Before proposing, reviewing, sequencing, or changing repository content:

1. Read all of `AGENTS_CORE.md`.
2. Read the root `README.md` for the current implemented/planned status and developer entry points.
3. Read `docs/README.md` to identify the authoritative document for the work area.
4. Inspect the current GitHub issue, related pull requests, latest `main`, and active CI/review state.
5. Read the relevant focused documents before designing or changing that area.

Use the documentation as follows:

- `README.md`: concise repository status and entry points; not the detailed design source;
- `docs/README.md`: documentation index and ownership rules;
- `docs/PROJECT_REQUIREMENTS.md`: product scope and functional/non-functional requirements;
- `docs/MVP_ROADMAP.md`: MVP phases, issue breakdown, and default build order;
- `docs/HLD.md`: system architecture, major components, flows, and deployment view;
- `docs/LLD.md`: module boundaries, contracts, validation, persistence, and implementation design;
- `docs/OBSERVABILITY_LLD.md`: logging, metrics, tracing, correlation, and telemetry-safety design;
- `docs/PARSING_STRATEGY.md`: deterministic parsing, broad parser, AI fallback, validation, and review strategy;
- `docs/LOCAL_IDENTITY_PROVIDER.md` and `docs/LOCAL_OBSERVABILITY.md`: local operational procedures;
- `docs/LEARNING_GUIDE.md`: learning objectives, teaching expectations, and learning-track sequencing.

Do not read only `README.md` and infer the design. Do not duplicate detailed design into `AGENTS.md`.

GitHub and the current `main` branch are the source of truth for implementation state. If an issue, document, and current code disagree, identify and reconcile the inconsistency before implementation rather than silently following stale text.

### 9. Default dependency-ordered delivery sequence

Use dependency order rather than issue-number order. Before starting each issue, re-check open/closed state, prerequisites, current code, the roadmap, and any approved reprioritization.

The current default sequence is:

```text
#8 statement metadata persistence
→ #9 deterministic PDF extraction
→ #10 deterministic parsing pipeline (split into reviewable sub-issues where necessary)
→ #11 rule-based categorization
→ #12 validated transaction persistence
→ #43 AI client abstraction
→ #44 structured-output validation
→ #45 prompt templates and fixture-based evaluation
→ #42 AI parsing fallback
→ #13–#16 deterministic analytics
→ #20 deterministic anomaly detection
→ #19 AI categorization fallback
→ #17 refine and implement AI insight service
→ #18 AI insights API
→ #22 → #23 → #24 → #21 natural-language query pipeline
→ #25–#29 RAG and semantic retrieval
→ #46–#48 controlled agentic AI
→ #35–#40 frontend
→ #30–#34 additional ingestion and product automation
```

Rules for using this sequence:

- complete the deterministic ingestion and analytics foundations before AI, RAG, or agents depend on them;
- establish shared AI abstractions and validation before feature services call a provider;
- keep SQL/backend logic as the source of truth for financial calculations;
- split oversized issues into coherent, reviewable implementation units rather than creating one large PR;
- update `docs/MVP_ROADMAP.md` and this compact sequence when the approved delivery plan changes;
- security defects, production failures, dependency vulnerabilities, and explicitly approved priorities may supersede this default sequence;
- Issue #71 remains parked until its developer-experience work is explicitly prioritized.
