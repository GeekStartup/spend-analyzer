# 💰 Spend Analyzer

> A production-style, AI-powered personal finance intelligence platform for secure, multi-user spend analysis.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue)
![Auth](https://img.shields.io/badge/Auth-OAuth2%20%2F%20OIDC-purple)
![Status](https://img.shields.io/badge/Status-Planning%20%2F%20MVP%20Development-orange)

---

## 🚀 Overview

**Spend Analyzer** is a secure, containerized backend system that helps users analyze personal financial transactions from bank and credit card statements.

The system is designed as a real-world engineering project with:

- Secure authentication and authorization
- Multi-user data isolation
- PDF statement ingestion
- Structured transaction storage
- Deterministic financial analytics
- AI-powered insights and explanations
- Future support for RAG, email ingestion, SMS ingestion, and dashboards

This project is built with a strong focus on **clean architecture, extensibility, cloud-readiness, and interview-grade system design**.

> **Project status:** This repository is currently in planning and MVP development phase. Application code will be added incrementally through GitHub issues.

---

## 🎯 Problem Statement

Personal financial data is often scattered across:

- Bank account statements
- Credit card statements
- Emails
- SMS notifications
- Multiple accounts and users

This makes it difficult to answer questions like:

- Where is my money going every month?
- Which category has increased compared to last month?
- What are my top recurring expenses?
- Are there unusual or high-value transactions?
- How can I reduce spending?

**Spend Analyzer solves this by converting financial statements into structured, searchable, and intelligent financial insights.**

---

## 🧠 Product Vision

The long-term vision is to build a **personal financial intelligence platform** that can:

- Maintain month-on-month spend history
- Compare spending trends over time
- Detect anomalies and recurring payments
- Support natural language financial queries
- Use RAG for contextual financial reasoning
- Provide personalized recommendations

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
  ├── PDF Parsing
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
| **PostgreSQL** | Structured transaction and analytics data |
| **Identity Provider** | OAuth2 / OIDC-based authentication |
| **Docker** | Local and cloud-ready containerized runtime |
| **AI Provider** | Insight generation and future query intelligence |
| **PDF Parser** | Extracts transaction data from statements |

---

## ✨ Key Features

### 🔐 Secure Multi-user Access

- OAuth2 / OIDC-based authentication
- JWT-protected APIs
- User-level data isolation
- Every transaction linked to an authenticated user

### 📥 Statement Ingestion

- Upload PDF bank or credit card statements
- Extract text and tabular data
- Parse transactions into structured records
- Store transaction history for future analysis

### 📊 Financial Analytics

- Monthly spend summary
- Category-wise breakdown
- Merchant-level analysis
- Income vs expense calculation
- Month-on-month comparison
- Historical trend tracking

### 🧠 AI-Powered Insights

AI is used to explain and reason over already calculated data.

Examples:

- Food spending increased significantly this month.
- A large one-time transaction caused the spike in expenses.
- Recurring subscription expenses are increasing.

> Financial calculations are always deterministic and performed using backend logic or SQL. AI is not trusted as the source of numerical truth.

---

## 🔎 Future Natural Language Querying

Planned support for questions like:

```text
How much did I spend on food last month?
Which merchant did I spend the most on?
Why was my credit card bill high this month?
Compare my travel expenses for the last 3 months.
```

---

## 🧠 AI Design Philosophy

```text
SQL calculates.
Backend validates.
AI explains.
```

AI is used for:

- Insight generation
- Explanation
- Categorization fallback
- Natural language query interpretation
- Future RAG-based contextual reasoning

AI is **not** used for:

- Final financial totals
- Source-of-truth calculations
- Direct modification of transaction amounts

---

## 📁 Project Structure

```text
spend-analyzer/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── health.py
│   │   ├── ingestion.py
│   │   ├── summary.py
│   │   └── insights.py
│   ├── auth/
│   │   └── jwt.py
│   ├── db/
│   │   ├── connection.py
│   │   └── migrations/
│   ├── services/
│   │   ├── ingestion_service.py
│   │   ├── pdf_service.py
│   │   ├── transaction_service.py
│   │   ├── analytics_service.py
│   │   └── ai_service.py
│   └── models/
│       └── transaction.py
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
docker-compose up --build
```

### 4. Access the Application

| Service | URL |
|---|---|
| Backend API | `http://localhost:8000` |
| API Docs | `http://localhost:8000/docs` |
| Identity Provider | Configured locally through environment variables |

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
| `GET` | `/` | Application health check |
| `GET` | `/health/db` | Database connectivity check |
| `GET` | `/me` | Authenticated user details |
| `POST` | `/ingest` | Upload statement PDF |
| `GET` | `/transactions` | List user transactions |
| `GET` | `/summary?month=YYYY-MM` | Monthly summary |
| `GET` | `/comparison?month=YYYY-MM` | Month-on-month comparison |
| `GET` | `/insights?month=YYYY-MM` | AI-generated insights |
| `POST` | `/query` | Natural language financial query |

---

## 🧾 Data Model: Transaction

| Field | Description |
|---|---|
| `id` | Unique transaction ID |
| `user_id` | Authenticated user identifier |
| `transaction_date` | Date of transaction |
| `description` | Raw transaction description |
| `merchant` | Normalized merchant name |
| `category` | Spend category |
| `amount` | Transaction amount |
| `transaction_type` | Debit or credit |
| `account_name` | Source account or card |
| `source_file_id` | Reference to uploaded statement |
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
| AI | OpenAI API |
| PDF Parsing | pdfplumber |
| Future RAG | pgvector / vector search |
| Future Frontend | React / Vite |

---

## 🧪 Engineering Principles

- One responsibility per module
- Config-driven behavior
- No hardcoded secrets
- SQL for financial correctness
- AI for insight, not truth
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

🚧 Currently in MVP planning and development phase.

---

## 🏆 Author

**Ashish Nayak**

---

## 📄 License

This project is intended for personal learning, portfolio development, and production-style system design practice.
