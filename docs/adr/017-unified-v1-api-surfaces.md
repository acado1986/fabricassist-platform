# ADR-017: Unified v1 API surfaces

**Status:** Accepted  
**Date:** 2026-07-31  
**Supersedes:** ADR-016's allowance for simple GraphQL mutations and its
small-executor/non-normalized-cache assumption. ADR-016's modular monolith,
GraphQL-read, REST-command/upload, and durable SSE boundaries remain in force.

## Context

FabricAssist has one Expo application targeting web, iOS, and Android and one v1
API implemented by the existing FastAPI modular monolith. Separate transport
implementations or business rules per platform would create inconsistent state,
security behavior, and maintenance cost.

GraphQL is valuable for storefront composite reads, but write operations require
clear idempotency, authentication, upload, audit, destructive-workflow, and HTTP
semantics. REST writes also change data held by a normalized GraphQL client, so
cache synchronization must be deterministic. SSE provides live run events, but
PostgreSQL-backed GraphQL reads remain the canonical recovery point.

## Decision

FabricAssist exposes one unified v1 API with strict transport boundaries:

- `/api/v1/graphql` is one read-only Strawberry GraphQL schema for composite
  storefront queries used by web, iOS, and Android.
- `/api/v1/...` REST endpoints handle every write, authentication/session action,
  presigned upload/file operation, AI command, feedback action, identity
  decision, service event, and deletion.
- `/api/v1/runs/{id}/events` provides authenticated SSE run progress and validated
  display events.
- GraphQL mutations are deprecated/removed; no new mutation field is added.
- FastAPI controllers and Strawberry resolvers are thin DTO adapters over the
  same application service/query layer. They do not own ORM queries, tenant/user
  scoping, authorization, validation, or business behavior.
- GraphQL uses request-scoped Strawberry DataLoaders for batching and per-request
  lookup caching. Loader state never crosses requests or tenant boundaries.
- The shared Expo application uses Apollo Client with `InMemoryCache` as its one
  normalized GraphQL client, generated typed documents from
  `@graphql-codegen/client-preset`, and one auth/retry/error abstraction across
  all platforms. TanStack Query remains in use for generated REST operations.
- The Apollo cache is memory-only for the first production cutover and is
  cleared on logout, user change, or tenant change. Persistent normalized-cache
  storage requires a later privacy and lifecycle decision.
- Every storefront REST write declares its GraphQL cache effect in one typed
  registry. Unknown or safety-relevant effects trigger canonical GraphQL refetch
  rather than optimistic fabrication.
- Terminal SSE events and reconnects query canonical `activeAnalysis` and
  `progressPercent` state through GraphQL before presenting persistent completion
  or opening a new stream.
- GraphQL enforces opaque keyset pagination, request complexity limits,
  production introspection policy, sanitized errors, correlation IDs, tenant
  isolation, and object-key protection.

## Consequences

- The v1 GraphQL schema becomes query-only, even for small metadata changes such
  as garment rename/archive/unarchive.
- Existing GraphQL mutation callers must move to generated REST operations before
  mutation removal.
- REST-write cache effects become required implementation and test metadata for
  the shared Expo client.
- The current lightweight GraphQL executor must evolve to the shared Apollo
  Client configuration. Existing refresh-once behavior remains authoritative
  and is reused by Apollo links rather than reimplemented independently.
- Migrated REST controllers and GraphQL resolvers must be refactored away from
  direct ORM access into shared `GarmentService`, `ScanService`,
  `AnalysisRunService`, and application queries.
- SSE is transient UI state. GraphQL remains the canonical resynchronization
  point after terminal events and reconnects.
- Keeping existing REST reads during migration does not change the strict rule
  for new storefront composition; their retirement requires a separate decision.
- Production rollout must verify live-connection capacity, mobile reconnect
  behavior, normalized-cache correctness, generated-contract drift, and
  cross-tenant isolation.
