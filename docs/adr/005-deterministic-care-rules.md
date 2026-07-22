# ADR-005: Make deterministic rules authoritative

- **Status:** Superseded by [ADR-009](009-validator-gated-ai-care-plans.md)
- **Date:** 2026-07-20

## Context

Free-form model output cannot safely determine garment-care permissions,
prohibitions, temperatures, or professional-only processes.

## Decision

Vision models extract structured evidence validated by strict schemas. Only
versioned deterministic Python rules produce authoritative care and detergent
decisions. Prohibitions and explicit label evidence take precedence; uncertainty
or contradiction routes to retake/review behavior.

## Consequences

Rule changes require immutable versions and regression tests. No model or rule
implementation is part of Phase 1.
