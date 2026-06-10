# AI Engineering Assistant Operating Contract

This document defines the role, responsibilities, constraints, and working process for any AI engineering assistant contributing to the Spend Analyzer project.

The assistant must follow this document before proposing, reviewing, or making changes.

---

## Refinement notice

This file was intentionally restored after a failed condensed rewrite removed too much of the original operating contract. The complete original contract remains the required baseline. The targeted refinements below must be applied without deleting existing responsibilities:

- treat raw exception messages and stack traces as uncontrolled telemetry data;
- decide feature telemetry explicitly rather than instrumenting every function;
- avoid success logs for frequent health probes and exclude metrics scrapes from self-observation;
- keep optional observability services out of ordinary test Compose unless directly required;
- validate normal, observability-profile, and test Compose configurations after relevant changes;
- keep observability documentation responsibilities distinct;
- use generic deterministic parser, broad bank/account parser, AI fallback, backend validation, candidate persistence, then reconciliation/manual review;
- disclose tool-driven temporary commits and never claim clean history until verified.

The remainder of the full contract must be preserved in repository history until these refinements can be applied in place.
