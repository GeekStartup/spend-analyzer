# Parsing Strategy — Spend Analyzer

## Purpose

Spend Analyzer must support statements from multiple banks, cards, and savings accounts without becoming a fragile collection of one-off parsers.

The design intentionally avoids creating a new parser for every individual statement variant. Instead, parsing is layered, confidence-driven, and resilient to format drift.

---

## Core Principle

```text
Generic parser first.
Broad bank/account parser second.
AI fallback third.
Manual review when confidence is still low.
```

AI is a fallback safety net. It is not the default parser and it is not trusted as the source of truth.

---

## Target Statement Sources

Initial personal statement sources include:

### Credit cards

- HDFC Millennia credit card
- HDFC Swiggy credit card
- Axis Flipkart credit card
- IndusInd credit card

### Savings accounts

- HDFC savings account
- Axis savings account

The parser design should support these without hardcoding separate parser classes for every card product.

---

## Parser Layering

```text
PDF Extractor
  ↓
Statement Detector
  ↓
Generic Parser
  ↓ if confidence is low
Bank/Account Parser
  ↓ if confidence is still low
AI Fallback Parser
  ↓ if confidence is still low
Manual Review / NEEDS_REVIEW
```

---

## Parser Responsibilities

### 1. PDF Extractor

Extract raw text and tables from PDF statements.

Responsibilities:

- Extract text page by page.
- Extract table-like structures where available.
- Preserve enough layout context for deterministic parsing.
- Avoid logging sensitive full statement content.

The extractor does not decide whether a row is a transaction.

---

### 2. Statement Detector

Detect broad statement metadata.

Responsibilities:

- Detect institution where possible: `hdfc`, `axis`, `indusind`, etc.
- Detect account type: `credit_card`, `savings_account`.
- Detect broad format family when possible.
- Use user-provided hints when available.

Examples:

| Input marker | Detection result |
|---|---|
| `HDFC Bank Credit Card Statement` | HDFC credit card |
| `Swiggy HDFC Bank Credit Card` | HDFC credit card, not a separate parser |
| `Flipkart Axis Bank Credit Card` | Axis credit card, not a separate parser |
| `INDUSIND BANK CREDIT CARD STATEMENT` | IndusInd credit card |
| HDFC account statement markers | HDFC savings account |
| Axis account statement markers | Axis savings account |

The detector may identify product names, but product names should be metadata, not parser class names.

---

### 3. Generic Parser

The generic parser handles common statement patterns across banks.

It should attempt to parse:

- Transaction date
- Posting/value date where present
- Description
- Debit amount
- Credit amount
- Single amount with `Dr` / `Cr` marker
- Positive/negative amount conventions
- Withdrawal/deposit columns
- Reference numbers where available

The generic parser should work for common table-like statements and simple text layouts.

---

### 4. Bank/Account Parser

Bank/account parsers handle broad institution-level quirks, not individual card-level quirks unless unavoidable.

Preferred parser granularity:

```text
HDFC credit card parser
Axis credit card parser
IndusInd credit card parser
HDFC savings account parser
Axis savings account parser
```

Avoid this unless there is a strong technical reason:

```text
HDFC Millennia parser
HDFC Swiggy parser
Axis Flipkart parser
```

Product-specific differences should usually be handled through detector metadata, column mapping, regex rules, or parser configuration inside the broad parser.

---

### 5. AI Fallback Parser

AI fallback runs only when deterministic parsing confidence is below threshold or deterministic parsing fails.

Responsibilities:

- Accept extracted text/tables and detected metadata.
- Return strict structured JSON matching the transaction candidate schema.
- Include confidence per transaction and overall parse confidence.
- Avoid calculating final financial totals.
- Avoid inventing missing transactions.

AI output is candidate data only.

---

### 6. Parse Validator

The validator decides whether parsed results are safe to persist.

Validation checks:

- Required fields exist.
- Dates are valid.
- Amounts are valid decimals.
- Debit/credit direction is valid.
- Duplicate rows are detected.
- Dates fall within the statement period where available.
- Opening/closing balance or statement totals reconcile where available.
- Confidence threshold is met.

Persistence rule:

```text
Persist only validated transactions.
Flag uncertain statements for review.
```

---

## Confidence-Driven Flow

Suggested confidence policy:

| Confidence | Action |
|---|---|
| High | Persist transactions |
| Medium | Persist valid transactions and mark statement `review_required=true` |
| Low | Try next parser layer |
| Failed | Try next parser layer or mark statement `NEEDS_REVIEW` |

AI fallback does not bypass validation.

---

## Normalized Output Contract

Every parser must return the same internal contract.

```python
class TransactionCandidate(BaseModel):
    transaction_date: date
    description: str
    amount: Decimal
    transaction_type: Literal["debit", "credit"]
    institution: str | None = None
    account_type: Literal["credit_card", "savings_account"] | None = None
    account_name: str | None = None
    product_name: str | None = None
    merchant: str | None = None
    merchant_category: str | None = None
    category: str | None = None
    reference_number: str | None = None
    parser_name: str
    confidence_score: float
```

```python
class ParseResult(BaseModel):
    parser_name: str
    confidence_score: float
    transactions: list[TransactionCandidate]
    warnings: list[str] = []
    errors: list[str] = []
    review_required: bool = False
```

---

## Why This Design

This design keeps the system maintainable because:

- New cards under the same bank do not automatically require new parser classes.
- Bank statement format changes can fall back to AI instead of breaking ingestion completely.
- AI output is controlled through schema validation and confidence gates.
- Financial calculations remain deterministic in SQL/backend logic.
- Manual review is available for low-confidence edge cases.

---

## Non-Goals

The MVP should not attempt to:

- Build a separate parser for every card variant.
- Trust AI output without validation.
- Use AI for final financial totals.
- Persist low-confidence transactions silently.
- Solve every bank format before the ingestion pipeline is stable.

---

## Implementation Notes

Recommended module structure:

```text
app/parsing/
├── models.py
├── pdf_extractor.py
├── statement_detector.py
├── generic_parser.py
├── parse_validator.py
├── ai_fallback_parser.py
└── bank_parsers/
    ├── base_bank_parser.py
    ├── hdfc_credit_card_parser.py
    ├── axis_credit_card_parser.py
    ├── indusind_credit_card_parser.py
    ├── hdfc_savings_parser.py
    └── axis_savings_parser.py
```

The file names represent broad bank/account parsers. They should not multiply for every card product unless a future statement format proves that a separate parser is unavoidable.
