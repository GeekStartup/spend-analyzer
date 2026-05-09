# 💰 Spend Analyzer [![Build](https://github.com/GeekStartup/spend-analyzer/actions/workflows/build.yml/badge.svg?branch=main&event=push)](https://github.com/GeekStartup/spend-analyzer/actions/workflows/build.yml)

> A production-style personal finance intelligence backend for secure, multi-user spend analysis from bank and credit card statements.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue)
![Auth](https://img.shields.io/badge/Auth-OAuth2%20%2F%20OIDC-purple)
![Status](https://img.shields.io/badge/Status-MVP%20Development-orange)

---

## 🚀 Overview

**Spend Analyzer** is a secure, containerized backend system that helps users analyze personal financial transactions from bank account and credit card statements.

The system is designed with real-world backend architecture principles:

- Secure OAuth2 / OIDC authentication
- Multi-user data isolation
- PDF statement ingestion
- Support for different statement formats
- Generic and bank-specific parsing
- AI-assisted parsing fallback when deterministic parsing fails
- Structured transaction storage
- Deterministic financial analytics
- AI-powered explanations and insights in later MVPs

> **Project status:** MVP development in progress. Work is tracked through GitHub issues.

---

## 🎯 Problem Statement

Personal financial data is scattered across multiple sources:

- Credit card statements
- Savings account statements
- Multiple banks
- Multiple users in the same family
- Emails and SMS alerts in future phases

Statement formats vary significantly across banks and may change over time. A rigid parser for every individual card or account would be difficult to maintain.

**Spend Analyzer solves this by converting statements into a common normalized transaction model using a resilient parsing pipeline.**

---

## 🧠 Product Vision

The long-term vision is to build a personal financial intelligence platform that can:

- Maintain month-on-month spend history
- Compare spending trends over time
- Detect anomalies and recurring payments
- Support natural language financial queries
- Use RAG for contextual financial reasoning
- Provide personalized spending insights

---

## 🧱 High-Level Architecture

```text
Client
  │
  ▼
Identity Provider (OAuth2 / OIDC)
  │
  ▼
FastAPI Backend
  │
  ├── Authentication & User Context
  ├── Statement Ingestion
  ├── PDF Text/Table Extraction
  ├── Generic Parser
  ├── Bank-Specific Parser
  ├── AI Parsing Fallback
  ├── Validation & Review Gate
  ├── Transaction Processing
  ├── Analytics Engine
  └── AI Insight Engine
  │
  ▼
PostgreSQL
```

---

## 🧩 Core Components

| Component | Responsibility |
|---|---|
| **FastAPI Backend** | API layer, orchestration, and business logic |
| **PostgreSQL** | Structured statement, transaction, and analytics data |
| **Identity Provider** | OAuth2 / OIDC authentication and token issuing |
| **Docker** | Local and cloud-ready containerized runtime |
| **PDF Extractor** | Extracts text and table content from statement PDFs |
| **Generic Parser** | Extracts common transaction patterns across statements |
| **Bank Parsers** | Handles bank-level quirks for known institutions |
| **AI Parsing Fallback** | Extracts candidate transactions when deterministic parsing fails |
| **Validator** | Validates parsed transactions before persistence |
| **AI Provider** | GPT-based parsing fallback and later insight generation |

---

## ✨ Key Features

### 🔐 Secure Multi-user Access

- OAuth2 / OIDC-based authentication
- JWT-protected APIs
- User-level data isolation
- Every uploaded statement and transaction linked to an authenticated user

### 📥 Statement Ingestion

- Upload PDF bank or credit card statements
- Capture statement metadata such as institution, account type, account name, and statement format
- Extract text and tables from PDFs
- Parse transactions into a normalized internal model
- Store transaction history for future analysis

### 🧾 Resilient Parsing Strategy

The ingestion pipeline uses layered parsing:

```text
Generic Parser → Bank-Specific Parser → AI Fallback → Manual Review if needed
```

The goal is to avoid creating one hardcoded parser for every individual card while still handling real-world statement variation.

### 📊 Financial Analytics

- Monthly spend summary
- Category-wise breakdown
- Merchant-level analysis
- Income vs expense calculation
- Month-on-month comparison
- Historical trend tracking

### 🧠 AI Usage

AI is used carefully.

AI can be used for:

- Parsing fallback when deterministic parsers fail
- Categorization fallback
- Explanation and insight generation
- Natural language query interpretation
- Future RAG-based contextual reasoning

AI is **not** trusted blindly.

Financial calculations and final totals are always performed by backend logic or SQL.

---

## 🧠 AI Design Philosophy

```text
SQL calculates.
Backend validates.
AI assists.
```

AI-generated parsed transactions are treated as **candidate transactions**. They must pass backend validation before persistence.

Low-confidence parsing results should be marked for review instead of being silently saved.

---

## 📁 Project Structure

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
│       ├── pdf_extractor.py
│       ├── statement_detector.py
│       ├── generic_parser.py
│       ├── parse_validator.py
│       ├── ai_fallback_parser.py
│       └── bank_parsers/
│           ├── hdfc_credit_card_parser.py
│           ├── axis_credit_card_parser.py
│           ├── indusind_credit_card_parser.py
│           ├── hdfc_savings_parser.py
│           └── axis_savings_parser.py
│
├── docs/
│   ├── LLD.md
│   └── MVP_ROADMAP.md
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
└── .gitignore
```

---

## ⚙️ Getting Started

### 1. Clone Repository

```bash
git clone https://github.com/GeekStartup/spend-analyzer.git
cd spend-analyzer
```

### 2. Create Environment File

Create a local `.env` file using `.env.example` as a reference.

```bash
cp .env.example .env
```

> Do not commit `.env` to GitHub.

### 3. Start Services

```bash
docker compose up --build
```

### 4. Access the Application

| Service | URL |
|---|---|
| Backend Health | `http://localhost:8000/health` |
| Database Health | `http://localhost:8000/health/db` |
| API Docs | `http://localhost:8000/docs` |
| Identity Provider | `http://localhost:8080` in local development |

---

## 🧪 Testing

The project uses `pytest` for automated tests.

| Command | Purpose |
|---|---|
| `pytest` | Run fast/unit tests only |
| `pytest --integration` | Run Docker-backed integration tests only |
| `pytest --all` | Run both unit and integration tests |

Integration tests use `docker-compose.test.yml` to run the application with test infrastructure.

---

## 🔐 Authentication Flow

```text
1. User logs in through the identity provider.
2. Identity provider returns an access token.
3. Client sends the token to the backend.
4. Backend validates the token.
5. Backend extracts user identity.
6. APIs return only data belonging to that user.
```

API requests must include:

```http
Authorization: Bearer <access_token>
```

---

## 📡 Planned API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application health check |
| `GET` | `/health/db` | Database connectivity check |
| `GET` | `/me` | Authenticated user details |
| `POST` | `/ingest` | Upload statement PDF |
| `GET` | `/transactions` | List user transactions |
| `GET` | `/summary?month=YYYY-MM` | Monthly summary |
| `GET` | `/comparison?month=YYYY-MM` | Month-on-month comparison |
| `GET` | `/insights?month=YYYY-MM` | AI-generated insights |
| `POST` | `/query` | Natural language financial query |

---

## 🧾 Normalized Transaction Model

All parsers return the same transaction shape.

| Field | Description |
|---|---|
| `id` | Unique transaction ID |
| `user_id` | Authenticated user identifier |
| `statement_id` | Source statement reference |
| `transaction_date` | Date of transaction |
| `description` | Raw transaction description |
| `merchant` | Normalized merchant name |
| `category` | Spend category |
| `amount` | Transaction amount |
| `transaction_type` | Debit or credit |
| `institution` | Bank or card issuer |
| `account_type` | Credit card or savings account |
| `account_name` | User-friendly account/card name |
| `source_parser` | Parser used to extract the transaction |
| `confidence_score` | Parser confidence score |
| `created_at` | Record creation timestamp |

---

## 🗺️ MVP Roadmap

See [`docs/MVP_ROADMAP.md`](docs/MVP_ROADMAP.md) for the complete MVP breakdown and GitHub issue plan.

High-level roadmap:

1. **MVP 1 — Foundation**
2. **MVP 2 — PDF Ingestion**
3. **MVP 3 — Analytics**
4. **MVP 4 — AI Intelligence**
5. **MVP 5 — Natural Language Query Layer**
6. **MVP 6 — RAG and Semantic Search**
7. **MVP 7 — Automation**
8. **MVP 8 — Frontend**

---

## 🛠️ Tech Stack

| Area | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Authentication | OAuth2 / OIDC |
| Containerization | Docker, Docker Compose |
| AI | OpenAI GPT API |
| PDF Parsing | pdfplumber |
| Future RAG | pgvector / vector search |
| Future Frontend | React / Vite |

---

## 🧪 Engineering Principles

- One responsibility per module
- No hardcoded secrets
- Environment-driven configuration
- SQL for financial correctness
- AI for fallback and reasoning, not blind persistence
- Secure-by-default APIs
- User data isolation at every layer
- Docker-first local development
- Cloud-ready architecture

---

## ☁️ Cloud Readiness

The system is designed to be deployable to AWS in the future.

| Local Component | AWS Equivalent |
|---|---|
| FastAPI container | ECS / EC2 |
| PostgreSQL container | RDS PostgreSQL |
| Local PDF storage | S3 |
| Identity provider | Managed or self-hosted OIDC provider |
| Docker Compose | ECS task definitions |

---

## 📌 Project Status

🚧 Currently in MVP development phase.

---

## 🏆 Author

**Ashish Nayak**

---

## 📄 License

This project is intended for personal learning, portfolio development, and production-style system design practice.
