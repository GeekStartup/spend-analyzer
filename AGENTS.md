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
