# ADR-003: Use Valkey for transient coordination

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

The platform needs transient caching, rate limits, bounded locks, and initial
job coordination while preserving completed results durably.

## Decision

Use Valkey behind adapters for transient concerns. Use the `fabricassist:` cache
namespace. PostgreSQL remains authoritative; Valkey is never the only store for
completed business data.

## Consequences

Valkey loss may reduce performance or require redispatch but cannot erase final
records. Queue and cache behavior are implemented in their later owning phases.
