# ADR-012: Keep contextual conversation state in PostgreSQL

- **Status:** Accepted
- **Date:** 2026-07-22

## Context

Users need to ask follow-up questions about the same garment, its uploaded
images, prior answers, new stains, and previous service. Provider-side
conversation IDs are not portable, auditable, reliably deletable, or sufficient
as the business record.

## Decision

FabricAssist owns conversation threads and messages in PostgreSQL. A thread is
tenant/user scoped and tied to a physical garment plus the active evidence/result
revision. Model context is built from the versioned structured garment dossier,
validated plan, validation report, service history, a rolling summary, recent
messages, and only the raw images required for the current question.

Assistant messages use a strict schema containing natural-language text,
actionable claims, evidence references, uncertainty, and follow-up questions.
Every safety-relevant claim passes the same deterministic validator as the
initial plan. Provider conversation state may optimize an adapter, but it is
never the sole context or durable record.

## Consequences

- Conversation tables, job states, model-run operation metadata, pagination,
  rate limits, retention, deletion, and audit behavior are required.
- Rolling-summary prompt/schema versions must be recorded so context changes are
  explainable.
- Raw images are not resent on every turn, reducing privacy exposure, latency,
  and cost.
- New evidence creates a new analysis revision; the thread records which
  revision each assistant answer used.
