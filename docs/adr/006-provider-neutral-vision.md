# ADR-006: Use a provider-neutral vision boundary

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Model choice, hosting, privacy, cost, and latency may change, and local startup
must not require a paid service.

## Decision

Define a provider port outside the domain. Use a deterministic mock by default
and support an OpenAI-compatible HTTP adapter later without coupling domain code
to one vendor.

## Consequences

Provider selection remains configurable and replaceable. Phase 1 makes no model
calls and introduces no provider dependency or credential.
