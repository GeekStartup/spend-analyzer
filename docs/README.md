# Documentation Index — Spend Analyzer

This directory contains project-level documentation. Each file has a distinct purpose and should not duplicate implementation details unnecessarily.

| Document | Purpose |
|---|---|
| [`PROJECT_REQUIREMENTS.md`](PROJECT_REQUIREMENTS.md) | Product scope, learning objectives, functional requirements, and non-functional requirements |
| [`HLD.md`](HLD.md) | High-level architecture, system context, runtime view, major flows, ERD, AI/RAG view, and deployment view |
| [`LLD.md`](LLD.md) | Low-level backend design, modules, API design, data model, and non-functional design notes |
| [`MVP_ROADMAP.md`](MVP_ROADMAP.md) | MVP phases, issue breakdown, build order, and delivery plan |
| [`PARSING_STRATEGY.md`](PARSING_STRATEGY.md) | Detailed parsing strategy for generic, bank/account-specific, AI fallback, and manual review flows |
| [`LOCAL_IDENTITY_PROVIDER.md`](LOCAL_IDENTITY_PROVIDER.md) | Local Keycloak/OIDC setup, token generation, realm import, and test URLs |
| [`LOCAL_OBSERVABILITY.md`](LOCAL_OBSERVABILITY.md) | Local logs, metrics, traces, PostgreSQL observability, request-ID debugging, and safe telemetry rules |
| [`LEARNING_GUIDE.md`](LEARNING_GUIDE.md) | Source of truth for learning objectives, learning phase sequencing, issue-quality expectations, and Python/backend/AI/RAG/agent learning guidance |

## Documentation Rules

- Keep `README.md` at the repository root as a short landing page that points to this documentation index.
- Keep requirements in `PROJECT_REQUIREMENTS.md`.
- Keep high-level architecture, major flows, and diagrams in `HLD.md`.
- Keep implementation-level design in `LLD.md`.
- Keep parser-specific decisions in `PARSING_STRATEGY.md`.
- Keep operational setup details in focused runbooks such as `LOCAL_IDENTITY_PROVIDER.md` and `LOCAL_OBSERVABILITY.md`.
- Keep learning objectives and sequencing in `LEARNING_GUIDE.md`.
