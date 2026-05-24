# Spend Analyzer [![Build](https://github.com/GeekStartup/spend-analyzer/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/GeekStartup/spend-analyzer/actions/workflows/build.yml?query=branch%3Amain)

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue)
![Auth](https://img.shields.io/badge/Auth-OAuth2%20%2F%20OIDC-purple)
![Status](https://img.shields.io/badge/Status-MVP%20Development-orange)

Spend Analyzer is a learning-first personal finance backend for secure, multi-user spend analysis from bank and credit card statements.

The project is built to practice production-style backend engineering with Python, FastAPI, PostgreSQL, Docker, OAuth2/OIDC, automated quality gates, and later AI-assisted parsing, RAG, and controlled agentic workflows.

## Current status

MVP development is in progress.

Implemented so far:

- FastAPI backend application
- PostgreSQL connectivity and Flyway migrations
- Local Keycloak/OIDC setup
- JWT-protected APIs
- Health and authenticated user endpoints
- Authenticated PDF statement upload
- Local file storage for uploaded statements
- Strict CI checks for linting, formatting, security, dependency audit, tests, and coverage

Planned later:

- Statement metadata persistence
- PDF extraction and transaction parsing
- AI fallback parsing
- Spend analytics APIs
- Natural language query layer
- RAG and controlled finance agent
- Frontend

## Documentation

Start with the documentation index:

- [Documentation index](docs/README.md)
- [Project requirements](docs/PROJECT_REQUIREMENTS.md)
- [High-level design](docs/HLD.md)
- [Low-level design](docs/LLD.md)
- [Parsing strategy](docs/PARSING_STRATEGY.md)
- [MVP roadmap](docs/MVP_ROADMAP.md)
- [Local identity provider](docs/LOCAL_IDENTITY_PROVIDER.md)
- [Learning guide](docs/LEARNING_GUIDE.md)

## Quickstart

Create a local environment file:

```bash
cp .env.example .env
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Start the local stack:

```bash
docker compose up --build
```

Useful local endpoints:

| Service | URL |
|---|---|
| Backend health | `http://localhost:8000/health` |
| Database health | `http://localhost:8000/health/db` |
| API docs | `http://localhost:8000/docs` |
| Local identity provider | `http://localhost:8080` |

## Tests and quality checks

Run all tests:

```bash
pytest
```

Run the same quality gates used by CI:

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

- Line coverage must be at least 95%.
- Branch coverage must be at least 95%.

## Engineering principles

- Derive user identity from validated tokens.
- Keep financial calculations deterministic.
- Treat AI output as candidate data until backend validation passes.
- Keep PRs small and scoped.
- Keep learning objectives explicit for each issue.
