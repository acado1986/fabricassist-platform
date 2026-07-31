# ADR-016: Mixed GraphQL, REST, and SSE API

**Status:** Accepted  
**Date:** 2026-07-31  
**Decision:** Keep FabricAssist as one FastAPI modular monolith while adding
GraphQL for canonical frontend reads/simple metadata mutations, REST for
presigned uploads and AI commands, and SSE for durable AI-run progress.

## Context

REST/OpenAPI remains the existing command contract, direct private object upload
is required by ADR-007, and all safety-relevant results remain PostgreSQL-backed
and validator-gated. The Expo client already uses TanStack Query; it does not
need Apollo merely to send GraphQL requests.

## Decision

- Mount Strawberry GraphQL at `/api/v1/graphql` in the existing API process.
- Keep REST routes under `/api/v1`, including upload, analysis/run, cancellation,
  retry, and operational endpoints. Old analysis/message routes remain wrappers
  during migration.
- Expose `GET /api/v1/runs/{run_id}/events` as authenticated fetch-based SSE.
  Store replayable lifecycle and post-validation message chunks in PostgreSQL;
  keep heartbeats, locks, rate limits, and cache data transient.
- Use `@graphql-codegen/client-preset` plus TanStack Query and the shared
  authenticated fetch/refresh behavior. Do not add Apollo.
- Preserve resource names (`Scan`, `Garment`, revisions, messages) rather than
  create a parallel session model.

## Consequences

FastAPI OpenAPI and its generated REST client remain required. GraphQL has depth
limits and production introspection disabled. SSE has a polling/recovery path,
and must be validated against the actual Render/proxy deployment before becoming
the default UX. The assistant never streams provider tokens before deterministic
validation and persistence.
