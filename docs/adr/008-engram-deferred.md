# ADR-008: Defer application memory beyond PostgreSQL and cache layers

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

The MVP requires auditable evidence reuse, not an autonomous agent-memory
system.

## Decision

Use PostgreSQL for durable evidence/results and implement cache layers in the
approved exact-image, perceptual-candidate, canonical-signature, and rendered
answer order. Defer semantic retrieval until sufficient approved data exists.
Engram is not an application runtime dependency.

## Consequences

No additional memory service or proprietary vector store is introduced. Any
future semantic layer remains candidate-only and cannot override safety facts.
