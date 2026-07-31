# Implementation task: production v1 storefront API migration

**Status:** Planned  
**Created:** 2026-07-31  
**Intended executor:** GPT-5.6 Luna (high reasoning)  
**Suggested branch:** `feat/v1-storefront-graphql-reads`  
**Authoritative decision:** [ADR-017](../adr/017-unified-v1-api-surfaces.md)  
**Related:** [ADR-016](../adr/016-mixed-graphql-rest-sse-api.md),
[Parent mixed-transport task](mixed-graphql-rest-sse-api.md),
[GraphQL garment-history migration](graphql-garment-history-migration.md),
[requirements](../requirements.md), [architecture](../architecture.md)

## Authority and execution rules

ADR-017 and this task are authoritative for the remaining storefront migration.
They supersede older guidance that allowed GraphQL metadata mutations, prohibited
a normalized GraphQL client, or treated REST polling as the canonical live-run
recovery path.

When implementing this task:

1. Before editing, read `AGENTS.md`, `docs/requirements.md`,
   `docs/architecture.md`, ADR-017, this task, and any nearer nested
   `AGENTS.md` completely.
2. Inspect the working tree and current implementation; do not assume the
   baseline described below is the complete diff.
3. Execute Phases 1 through 7 in order.
4. Keep every phase as a coherent, reviewable vertical slice.
5. Do not start a later phase while the current phase's acceptance gate is
   failing.
6. Preserve existing REST reads throughout this task; retiring them requires a
   separate approved task.
7. Do not rewrite unrelated routes or application modules merely to remove
   pre-existing architecture debt.
8. Run and record the focused checks for each phase. Never claim an unavailable
   platform, deployment, or capacity check passed.
9. Stop and report rather than bypassing a security, tenant-isolation,
   deterministic-validation, generated-contract, or production-capacity failure.
10. Preserve user changes already present in the working tree.
11. After each phase, report changed files, commands actually run, measured
    results, remaining risks, and whether the acceptance gate passed.

## Goal

Establish one production-ready FabricAssist **v1 API** powering the shared Expo
application on web, iOS, and Android. Migrate storefront composite reads to a
single read-only GraphQL schema while preserving REST for every write and SSE
for real-time run events.

The v1 API consists of three transport surfaces in the existing FastAPI modular
monolith:

```text
/api/v1/graphql               GraphQL composite reads only
/api/v1/...                   REST writes, auth, uploads, commands, and files
/api/v1/runs/{id}/events      SSE run progress and validated display events
```

This task changes transport adapters and first-party call sites. It does not
change deterministic care validation, garment identity semantics, PostgreSQL
authority, object-storage privacy, retention, or provider selection.

The expected performance benefit comes from fewer mobile round trips, bounded
SQL query counts, and normalized-cache reuse. GraphQL is not assumed to be
faster merely because it replaces REST. Every migration phase must measure its
effect and may leave an optional read on its current transport when measurement
shows no benefit.

## Current implementation baseline

Retain and build on these working foundations:

- Strawberry is mounted at `/api/v1/graphql` with authentication, sanitized
  errors, correlation IDs, depth/token/alias limits, and production
  introspection policy.
- GraphQL Code Generator uses `@graphql-codegen/client-preset` and the repository
  provides `make graphql`, `make check-graphql-drift`, and
  `make check-graphql-breaking`.
- The shared Expo client already uses generated GraphQL documents for garment
  history, conversation reads, and scan/run recovery.
- `garmentHistory` already uses a timestamp-plus-UUID opaque keyset cursor and a
  batched projection.
- REST generated OpenAPI operations already perform storefront writes, uploads,
  authentication, identity decisions, feedback, and deletion.
- `GET /api/v1/runs/{id}/events` already provides PostgreSQL-backed ordered
  events, heartbeats, replay identifiers, short-lived database sessions, and
  connection metrics.
- The shared Expo package already has a fetch-based SSE parser and transport.

Known gaps that this task must close:

- The GraphQL schema still exposes `Mutation` fields.
- Most GraphQL resolvers and affected REST controllers access SQLAlchemy and ORM
  models directly.
- `application/garment_history.py` contains SQLAlchemy infrastructure code.
- There are no request-scoped Strawberry DataLoaders.
- The Expo GraphQL executor has no normalized entity cache.
- There is no exhaustive REST-write-to-GraphQL cache-effect registry.
- `result.tsx` still reads scan detail, result detail, and identity candidates
  through REST.
- `garments/[garmentId].tsx` still reads garment and scan history through REST.
- `images.tsx` still reads image metadata through REST.
- SSE reconnect opens a new stream without first awaiting canonical GraphQL
  recovery; failed and cancelled terminal events do not trigger the same
  canonical synchronization as completion.
- Existing GraphQL tests are primarily SDL/unit tests, and SSE tests do not cover
  authenticated HTTP streaming, replay, ownership, reconnect, or fallback.

## Architecture split

### Strict transport boundary

```text
Shared Expo application (web, iOS, Android)
        │
        ├── GraphQL /api/v1/graphql
        │     read-only composite screen queries
        │
        ├── REST /api/v1/...
        │     every write, auth, upload, command, deletion, and file action
        │
        └── SSE /api/v1/runs/{id}/events
              transient live progress and validated display events

GraphQL resolver     REST controller      SSE controller
        \                  |                    /
         \                 |                   /
          Application services and query services
       GarmentService / ScanService / AnalysisRunService
                            |
                     Repository ports
                            |
               SQLAlchemy infrastructure adapters
                            |
                       PostgreSQL
```

FastAPI REST controllers, Strawberry GraphQL resolvers, and SSE controllers are
thin DTO transport adapters. They do not own business rules, ownership checks,
tenant scoping, transaction behavior, or database queries.

Application services and queries define transport-neutral DTOs and repository
ports. SQLAlchemy implementations belong in the infrastructure layer. For the
migrated surfaces, application modules must not import persistence ORM models or
SQLAlchemy sessions.

The GraphQL request context contains:

- the authenticated tenant/user principal;
- the correlation ID;
- `GarmentService`, `ScanService`, and `AnalysisRunService` or their query
  interfaces;
- request-scoped DataLoaders.

It must not expose an `AsyncSession` or object-storage implementation to
resolvers.

Review checklist:

- Does this change update the shared service/query, or patch only one transport
  adapter? An adapter-only business fix signals an incorrect boundary.
- Do REST and GraphQL apply the same tenant, user, archive/deletion, validation,
  provenance, and authorization rules?
- Does every write enter through REST?
- Does GraphQL expose only active, released, validator-approved customer state?
- Does the resolver/controller only map DTOs and sanitized errors?
- Is every loader scoped to one authenticated GraphQL request?

### One read-only GraphQL schema

The v1 API has one Strawberry GraphQL schema at `/api/v1/graphql` for all shared
Expo targets. It contains queries only.

The current Expo operations contain no GraphQL mutation caller. Verify that
inventory in Phase 1 and then remove the entire mutation root and mutation-only
input/output types. Do not preserve unused mutations merely to avoid an
intentional pre-production schema cutover.

- Do not add new GraphQL mutations or subscriptions.
- Keep schema generation deterministic through Strawberry and GraphQL Code
  Generator.
- Use generated typed documents; do not handwrite duplicate response or variable
  interfaces.
- Disable production introspection according to ADR-016/ADR-017.
- Enforce depth, token, alias, and measured query-cost limits.
- Existing REST read endpoints remain mounted during this task.

## Transport decision table

| Capability                                   | v1 transport        | Decision                                                                                    |
| -------------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------- |
| Garment history cards                        | GraphQL             | Typed, paginated composite read already used by the shared Expo screen.                     |
| Chat message history                         | GraphQL             | Ordered, opaque-cursor read; sending messages remains REST.                                 |
| Result detail                                | GraphQL             | Compose scan, validated result, active analysis, product evidence, and identity candidates. |
| Garment detail and analysis history          | GraphQL             | Compose identity, identifiers, analyses, service history, and safe thumbnails.              |
| Image metadata                               | GraphQL             | Return safe metadata only; image preview/download remains REST.                             |
| Current user and measured bootstrap reads    | GraphQL when proven | Migrate only when measurement removes a real request waterfall.                             |
| Register, login, refresh, logout             | REST                | Authentication and session handling remain explicit HTTP operations.                        |
| Create scan                                  | REST                | Begins an upload and analysis command workflow.                                             |
| Presigned upload instructions and completion | REST                | Preserve direct S3/R2-compatible upload semantics and headers.                              |
| Image preview/download                       | REST/object storage | Preserve file, content type, disposition, and short-lived URL semantics.                    |
| Start, retry, or cancel AI run               | REST                | Long-running idempotent commands with explicit lifecycle behavior.                          |
| Send chat message                            | REST                | Auditable asynchronous command; conversation reads remain GraphQL.                          |
| Product lookup execution                     | REST                | External-provider command with timeout, validation, and SSRF controls.                      |
| Confirm/reject identity candidate            | REST                | Auditable identity decision.                                                                |
| Submit feedback/request review               | REST                | Workflow-changing write.                                                                    |
| Rename/archive/unarchive garment             | REST                | All writes use REST without exceptions based on mutation size.                              |
| Delete garment or scan                       | REST                | Destructive, auditable, retryable object/database workflow.                                 |
| Live AI run progress                         | SSE                 | `/api/v1/runs/{id}/events` carries transient progress and validated display events.         |
| Canonical state after live events            | GraphQL             | Every terminal event and reconnect performs canonical synchronization.                      |

## Backend requirements

### Shared service and repository boundary

REST controllers and GraphQL resolvers may:

- parse and validate transport DTOs;
- obtain authenticated request context and correlation ID;
- call one application command/query service;
- map typed application results into transport responses;
- translate expected failures into sanitized transport errors.

They must not:

- issue SQLAlchemy queries or use ORM sessions directly;
- implement tenant/user ownership decisions;
- select active revisions or validated results independently;
- construct provider or object-storage clients;
- duplicate idempotency, transaction, archive, deletion, or validation rules;
- expose object keys, raw provider payloads, rejected proposals, stack traces, or
  cross-tenant resource existence.

Extract direct ORM access only as a migration phase touches a surface. Do not
attempt a repository-wide application-layer rewrite in this task.

For `garmentHistory` specifically:

- keep cursor encoding/decoding, DTOs, and the query contract in the application
  layer;
- move SQLAlchemy statements and persistence-model imports to an infrastructure
  query adapter;
- inject that adapter through the composition root;
- make both REST compatibility reads and GraphQL use the same query contract.

### Request-scoped DataLoaders

Create Strawberry DataLoaders through the GraphQL context factory for repeated
lookups such as garments, scans, active revisions, validated results,
identifiers, service events, images, product evidence, and identity candidates.

- A DataLoader instance lives for one GraphQL request only.
- A loader is constructed with the authenticated principal; client input never
  selects a tenant.
- Batch queries include tenant and user ownership filters and return results in
  the same order as requested keys.
- Missing and unauthorized keys produce the same nullable/not-found behavior.
- Batch functions call application query ports rather than embedding database
  behavior in resolvers.
- Query count remains O(1) with respect to page size.

Use a DataLoader only when GraphQL field composition would otherwise repeat a
lookup. A top-level application query that already returns one fully batched
projection must not be split into unnecessary per-field loaders.

### Pagination and stable state

- Use versioned opaque keyset cursors for every ordered GraphQL connection.
- Encode all authoritative sort components and a deterministic UUID tie-breaker.
- Do not use offset pagination.
- Do not use a UUID-only cursor when timestamp or status ordering is
  authoritative.
- Convert retained `scans`, `garments`, and `messages` connections from UUID
  cursors to opaque string cursors, or remove an unused connection through the
  approved schema-change process.
- Invalid or out-of-scope cursors return sanitized `INVALID_PAGINATION` errors
  without revealing resource existence.
- GraphQL returns only active, released, deterministically validated customer
  results. A rejected proposal is never readable as an approved result.
- Add database indexes only when an actual query plan demonstrates the need.

### Errors and observability

- Preserve stable sanitized GraphQL extension codes and correlation IDs.
- Return the same not-found behavior for absent and unauthorized resources.
- Never return database, provider, object-storage, or stack-trace details.
- Record operation name, duration, safe tenant/user/scan/run identifiers, SQL
  query count, DataLoader batch count, and error category.
- Do not log GraphQL variables containing sensitive visible text, complete
  presigned URLs, image bytes, tokens, or provider payloads.

## Frontend state management

### Selected unified Expo GraphQL client

Use **Apollo Client with `InMemoryCache`** as the one normalized GraphQL client
for web, iOS, and Android. Keep TanStack Query for generated REST operations.
Do not introduce urql or a second GraphQL client.

Place the shared Apollo construction, type policies, links, and cache-effect
application in `frontend/packages/api-client`. Mount one client through the
shared Expo authentication/composition root.

Requirements:

- Continue generating TypedDocumentNode operations through
  `@graphql-codegen/client-preset`.
- Configure normalized entity identities from stable `__typename` plus UUID
  `id`.
- Define cursor merge policies that preserve server ordering and deduplicate by
  entity ID/cursor.
- Preserve the existing shared refresh-once/session abstraction. Apollo auth and
  error links reuse it rather than creating a second refresh implementation.
- Handle both transport 401 and sanitized GraphQL authentication failures with
  at most one replay after a single-flight refresh.
- Retry only idempotent GraphQL queries on transient network failures, using
  bounded exponential backoff with jitter. Never use the GraphQL retry link to
  retry REST writes.
- Web retains existing secure cookie/token behavior.
- Native credentials use Expo SecureStore, never AsyncStorage.
- Keep the Apollo cache memory-only for this task.
- Clear the Apollo store on logout, user change, tenant change, or unrecoverable
  authentication failure. Do not allow one authenticated session to observe
  another session's cache.
- Measure and record web bundle-size and mobile-memory change before and after
  adding Apollo.

### REST-write cache-effect registry

Implement one typed registry mapping every REST write used by the shared Expo
application to its GraphQL cache effects. Screens and feature components must
not call generated REST write functions directly when doing so would bypass the
registry wrapper.

Every write has exactly one declaration:

- evict normalized entities;
- invalidate/refetch named canonical queries;
- clear authenticated cache;
- or explicit `noGraphQLEffect` with a documented reason.

Examples:

```text
REST operation                         Required GraphQL cache effect
DELETE /api/v1/garments/{id}           evict garment(id), refetch garmentHistory
PATCH/POST garment rename              refetch garmentDetail + garmentHistory
POST identity confirmation             refetch customerResult + garmentDetail
POST feedback/review request           refetch customerResult
POST upload completion                 refetch imageMetadata/result projections
POST run start/retry/cancel             refetch activeAnalysis/customerResult
POST/DELETE scan action                 refetch scan/result/history projections
login/logout/user change               clear or initialize authenticated cache
```

Requirements:

- Inventory customer, operator, and authentication REST writes used by the shared
  Expo codebase, including writes that can change a customer-visible result.
- A successful HTTP 2xx REST write invokes its effect automatically.
- Failed, aborted, or rejected writes do not invalidate successful canonical
  state.
- Safety-relevant results, identity decisions, deletions, service history, review
  outcomes, and run state default to network refetch rather than optimistic
  fabrication.
- Deletion evicts the entity, cleans dangling references, and then refetches
  affected connections.
- Add a lint/architecture test that prevents new storefront write call sites from
  bypassing the wrapper.
- CI fails when an inventoried REST write lacks a registry declaration and
  table-driven test.

### SSE and canonical synchronization

`/api/v1/runs/{id}/events` feeds transient progress UI and validated display
events. SSE data does not become the authoritative completed result.

Initial load and every reconnect use this order:

```text
network-only GraphQL run/result recovery
        ↓
update canonical normalized cache
        ↓
if the run is still active, open a new SSE connection
```

Terminal handling uses this order:

```text
RUN_COMPLETED / RUN_FAILED / RUN_CANCELLED
        ↓
stop the stream
        ↓
await network-only canonical GraphQL refetch
        ↓
render persistent terminal state
```

Additional rules:

- Do not reconnect using only a client-retained `lastEventId` or progress value.
- Existing durable event replay and `Last-Event-ID` support may remain, but
  correctness must not depend on uninterrupted stream history.
- Deduplicate replayed events by durable event sequence/ID after canonical
  recovery.
- Obtain a valid access token through the shared refresh coordinator before each
  connection attempt.
- Keep progress and stage updates in ephemeral screen/run state.
- Replace result-screen REST status polling with bounded, foreground-only,
  network-only GraphQL polling when streaming is unavailable.
- Pause streaming/polling in the background and perform GraphQL recovery before
  reconnecting in the foreground.
- Use the existing shared fetch-based Expo SSE parser unless platform testing
  proves it unreliable; do not add an EventSource polyfill without evidence.

## Detailed migration phases

### Phase 1 — contract, shared-core, and client foundation

**Goal:** remove contradictory guidance and establish the query-only/shared-core
foundation before migrating another screen.

Implementation:

1. Update the parent mixed-transport task so ADR-017 is explicitly authoritative.
2. Capture baseline measurements for result-screen network requests, representative
   GraphQL/REST latency, SQL query counts, web bundle size, and current SSE
   polling/reconnect behavior.
3. Verify that the shared Expo source contains no GraphQL mutation document or
   runtime mutation call.
4. Remove `Mutation`, mutation-only types, and mutation resolver code from
   `graphql_schema.py`. Keep every equivalent REST endpoint.
5. Add a schema test asserting no mutation root is exposed.
6. Introduce transport-neutral DTO/query/service contracts for the affected
   result, garment, image, and run surfaces.
7. Introduce infrastructure SQLAlchemy query adapters and composition-root
   injection. Do not move unrelated application debt.
8. Refactor `GraphQLContext` to expose the authenticated principal, correlation
   ID, services/queries, and request-scoped loaders—not `AsyncSession` or storage.
9. Add Apollo Client, `InMemoryCache`, shared auth/error/retry links, session
   cache clearing, and normalized type policies.
10. Add the typed REST-write cache-effect registry, wrapper, exhaustive current
    write inventory, and bypass-prevention test.
11. Add authenticated HTTP integration tests for `/api/v1/graphql`, including
    context construction, tenant isolation, sanitized errors, and correlation
    IDs.
12. Regenerate SDL and generated documents.

Intentional breaking-schema handling:

- Mutation-root removal is an approved ADR-017 cutover, but accidental query
  breakage remains forbidden.
- Extend the breaking-check workflow with a one-time, checked-in approval
  manifest bound to the old/new schema hashes, ADR-017, and the exact allowed
  mutation-root/mutation-only type removals.
- The normal default remains fail-closed.
- The approval must reject any removed or changed `Query` field, shared object
  field, enum value, or scalar.
- Never use `|| true`, disable GraphQL Inspector, or broadly ignore breaking
  changes.
- After the approved cutover, future schema changes must pass against the new
  query-only baseline without reusing the old approval.

**Acceptance gate:**

- The parent guidance no longer overrides ADR-017.
- `/api/v1/graphql` has no mutation root.
- Every existing write remains available through generated REST operations.
- Apollo is mounted once and clears state across authenticated-session changes.
- Every inventoried Expo REST write has a typed effect or justified explicit
  no-effect entry.
- GraphQL HTTP integration tests pass.
- Drift checks pass, and the only approved breaking differences are the exact
  ADR-017 mutation removals.
- Baseline measurements are recorded.

Do not start Phase 2 until this gate passes.

### Phase 2 — result composite read and run recovery

**Goal:** make `result.tsx` use one canonical GraphQL composite and reliable
GraphQL-first SSE recovery across web, iOS, and Android.

Implementation:

1. Add a result query composing scan status, `progressPercent`,
   `activeAnalysis`, released validated result, product evidence, identity
   candidates, and linked garment summary.
2. Implement it through `ScanService`/`AnalysisRunService` query contracts and
   infrastructure adapters.
3. Batch related records through request-scoped DataLoaders where the composite
   projection does not already batch them.
4. Replace result-screen REST reads for scan detail, result detail, and identity
   candidates with one generated GraphQL operation.
5. Keep identity decisions, feedback, deletion, start/retry/cancel, and all other
   writes on REST.
6. Register and test every result-screen REST write effect.
7. Extract the run stream/reconnect lifecycle from the screen into a focused
   shared hook/service that can be tested independently.
8. Implement network-only GraphQL recovery before initial/reconnect
   subscription.
9. Make completed, failed, and cancelled terminal events all await canonical
   refetch.
10. Replace REST polling fallback with bounded GraphQL polling.
11. Add authenticated SSE integration tests for authorization, tenant isolation,
    replay/deduplication, heartbeat, terminal close, disconnect cleanup, and
    database-session lifetime.
12. Test foreground/background and token-refresh behavior on web, Android, and
    iOS.

**Acceptance gate:**

- The canonical result load uses one GraphQL request instead of the current
  scan-detail/result/identity REST read sequence.
- All result writes remain REST and have tested cache effects.
- GraphQL recovery precedes every reconnect.
- All terminal event kinds synchronize persistent GraphQL state before terminal
  UI is presented.
- SQL query count remains bounded independently of related-row count.
- Normal metadata p95 remains below 500 ms under expected load and is no slower
  than the recorded baseline without an explained, approved tradeoff.
- The result screen has no REST status/result/identity polling fallback.

Do not start Phase 3 until this gate passes.

### Phase 3 — garment detail and paginated history

**Goal:** migrate `garments/[garmentId].tsx` and harden the existing garment
history without changing visible facts or history semantics.

Implementation:

1. Add an owner-scoped garment detail query containing verified identifiers,
   analysed-before and completed-cleaned facts, active analysis/result summary,
   service history, and safe thumbnails.
2. Add opaque keyset pagination for analysis/scan history with deterministic
   ordering and no duplicates or missing rows across page boundaries.
3. Split `application/garment_history.py` into an application DTO/query contract
   and infrastructure SQLAlchemy implementation.
4. Make compatible REST reads and GraphQL use the same garment query service.
5. Batch identifiers, revisions, events, and images where required.
6. Replace garment-screen REST reads with generated GraphQL operations.
7. Keep rename, archive, unarchive, service-event writes, and deletion on REST.
8. Register and test every garment write effect against `garmentDetail`,
   `garmentHistory`, and affected result projections.
9. Add non-contradiction tests between coexisting REST and GraphQL reads.

**Acceptance gate:**

- Garment detail/history reads are GraphQL-backed on every Expo target.
- `analysed_before` and `cleaned_before` remain semantically distinct.
- Garment application contracts contain no SQLAlchemy/persistence imports.
- REST writes deterministically refresh or evict every affected normalized view.
- Pagination and query-count tests pass for realistic multi-record histories.

Do not start Phase 4 until this gate passes.

### Phase 4 — image metadata reads

**Goal:** migrate `images.tsx` metadata reads while keeping files outside
GraphQL.

Implementation:

1. Expose only fields used by the screen: image ID, role, display order,
   dimensions, quality state, and safe metadata.
2. Load metadata through `ScanService` and a request-scoped loader or batched
   projection.
3. Replace metadata list REST reads with a generated GraphQL operation.
4. Keep preview/download URL acquisition and object access on REST/object
   storage.
5. Register upload/add/remove-image write effects.
6. Test authorization, retention state, cache effects, and response/log
   redaction.

**Acceptance gate:**

- Metadata uses GraphQL on all Expo targets.
- Preview/download remains REST/object storage.
- No storage key, image bytes, or complete presigned URL appears in GraphQL,
  errors, metrics, or logs.
- Image metadata latency and query count meet the recorded budgets.

Do not start Phase 5 until this gate passes.

### Phase 5 — measured current-user and bootstrap reads

**Goal:** compose authenticated startup reads only when measurement proves a
benefit.

Implementation:

1. Measure startup request waterfalls separately on web, Android, and iOS.
2. Add or expand a bootstrap GraphQL query only when it removes duplicate round
   trips without coupling unrelated feature lifecycles.
3. Keep register, login, refresh, logout, and session rotation on REST.
4. Preserve cookie security, SecureStore use, refresh-once behavior, correlation
   IDs, and Apollo store clearing.
5. Compare request count, p95 startup latency, bundle cost, and cache behavior
   against the Phase 1 baseline.

**Acceptance gate:**

- Startup is no slower on any Expo target.
- Every added bootstrap field removes a measured request or waterfall.
- Session and cross-user cache-isolation tests pass.
- If measurement shows no benefit, record a no-migration decision; that is a
  valid completion of this phase.

Do not start Phase 6 until this gate passes.

### Phase 6 — transport and cache hardening

**Goal:** prove the all-writes-on-REST rule and remove remaining adapter/cache
inconsistencies.

Implementation:

1. Re-inventory all shared Expo GraphQL operations and REST writes, including
   operator actions that affect customer-visible state.
2. Confirm no GraphQL mutation root, mutation document, or mutation runtime call
   remains.
3. Complete shared command-service extraction for affected REST writes; migrated
   controllers contain no ORM/business logic.
4. Complete registry coverage and table-driven tests for HTTP 2xx, failures,
   aborts, retries, idempotent repeats, deletion eviction, logout, and user
   change.
5. Convert retained UUID-only GraphQL cursors to opaque keyset cursors.
6. Add architecture checks for resolver/controller ORM access on migrated
   surfaces and for frontend registry bypasses.
7. Add REST/GraphQL non-contradiction tests for result detail, garment detail,
   identity candidates, image metadata, status, timestamps, validation state,
   and provenance.
8. Run security probes for unauthorized IDs/cursors and result publication.

**Acceptance gate:**

- The schema is query-only and every write uses REST.
- Every shared Expo REST write has a tested registry declaration.
- Migrated transport adapters contain no business logic or direct database
  access.
- All retained ordered GraphQL connections use opaque keyset cursors.
- No REST/GraphQL contradiction or cross-tenant existence leak is observed.

Do not start Phase 7 until this gate passes.

### Phase 7 — production validation and closeout

**Goal:** prove the unified v1 API under production-like cross-platform load and
record rollout evidence.

Implementation:

1. Run complete backend, frontend, generated-contract, web E2E, Android smoke,
   and iOS smoke validations.
2. Record per-operation GraphQL latency, SQL query count, DataLoader batch count,
   error rate, Apollo cache correctness, REST-write refetch behavior, bundle
   size, and mobile memory.
3. Ramp concurrent `/api/v1/runs/{id}/events` connections on the production
   hosting topology—for example 10, 25, 50, and 100—until the production latency
   or error budget is breached.
4. While connections are open, verify normal metadata requests remain below the
   required 500 ms p95, scan creation remains below one second p95, no unexpected
   5xx errors occur, and API requests are not starved.
5. Document the tested safe SSE connection limit, proxy buffering/timeout
   behavior, reconnect policy, and fallback behavior.
6. Verify unstable-network recovery on web, Android, and iOS.
7. Verify production introspection policy, query limits, tenant isolation,
   correlation IDs, log redaction, and object-key protection.
8. Update ADR/task completion records and the parent mixed-transport task with
   exact evidence.
9. Do not retire existing REST reads.

**Acceptance gate:**

- All Expo targets use the same transport/client rules.
- Production capacity and fallback behavior are measured and documented.
- Generated contracts and approved schema history are clean.
- Required tests pass; unavailable checks are explicitly reported and prevent a
  false completion claim.
- The parent task records remaining work accurately.

## Testing requirements

### Backend unit and integration tests

- Authenticated HTTP execution against `/api/v1/graphql`, including context
  construction and sanitized errors.
- Schema assertion that no mutation root exists.
- Tenant/user isolation and not-found equivalence for every query.
- Archived/deleted resource exclusion.
- Opaque cursor encode/decode, version handling, invalid cursor handling, null
  ordering, UUID tie-breaks, page boundaries, and no duplicates/missing records.
- DataLoader batch behavior, request-scoped cache lifetime, and isolation across
  sequential/concurrent users and tenants.
- SQL query-count ceilings for result, garment detail/history, and image
  metadata. Establish the measured ceiling per operation and require it to
  remain independent of page size.
- Result publication tests proving only active validated results are readable.
- Thumbnail/image tests proving object keys, bytes, and complete presigned URLs
  are absent from responses and logs.
- REST/GraphQL non-contradiction tests while read endpoints coexist.
- Authenticated SSE tests for replay, deduplication, ownership, heartbeat,
  terminal events, disconnect cleanup, and session lifetime.
- REST regression tests remain enabled.

### Frontend tests

- One Apollo configuration works on web, iOS, and Android.
- Apollo cache is cleared on logout, user change, tenant change, and terminal
  authentication failure.
- Generated documents compile without handwritten duplicate API interfaces.
- Cursor merge policies preserve order and avoid duplicate entities.
- Component tests cover loading, error, empty, populated, retry, localization,
  accessibility, and navigation states for every migrated screen.
- Table-driven cache-registry coverage for every shared Expo REST write.
- HTTP 2xx invokes the exact effect; failed/aborted writes do not.
- Lint/architecture tests reject write-registry bypasses.
- Completed, failed, and cancelled SSE events trigger awaited canonical refetch.
- Reconnect queries `activeAnalysis`/`progressPercent` before opening SSE.
- SSE replay/deduplication, foreground/background behavior, token refresh, and
  GraphQL polling fallback are tested.
- Image preview/download tests prove REST/object-storage use remains intact.
- Critical web E2E: scan → upload → run → result → history → garment detail →
  delete.
- Android and iOS smoke coverage for the same critical flow before completion.

### Security and operational tests

- GraphQL depth, token, alias, and query-cost limits.
- Production introspection policy.
- REST, GraphQL, and SSE authentication/authorization consistency.
- Rate/concurrency behavior for auth, writes, queries, and live connections.
- Cross-tenant ID and cursor probing.
- Correlation-ID propagation through all transports and application services.
- Log-redaction checks for credentials, image data, provider payloads, object
  keys, and complete presigned URLs.
- Production live-connection capacity and starvation test.
- Apollo cross-session cache-isolation test.

## CI and drift control

These commands remain mandatory:

```bash
make graphql
make check-graphql-drift
make check-graphql-breaking
```

For every schema or document change:

- Export SDL from Strawberry; never hand-edit
  `docs/api/graphql/schema.graphql`.
- Regenerate `frontend/packages/api-client/src/graphql/generated/`.
- Fail when generated artifacts differ from committed output.
- Run breaking-change comparison before merging.
- Use the one-time hash-bound ADR-017 approval only for the exact query-only
  schema cutover.
- Fail all unapproved future breaking changes.

Focused validation during implementation:

```bash
cd backend && uv run pytest tests/unit/test_graphql_schema.py
cd backend && uv run pytest tests/unit/test_run_events.py
cd backend && uv run pytest tests/unit
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build:web
make lint
make test
make check
```

Also run:

- authenticated PostgreSQL-backed GraphQL/SSE integration tests;
- OpenAPI drift checks when REST controllers or DTOs change;
- database migration tests whenever a measured query plan requires an index;
- web E2E plus Android/iOS smoke checks in Phase 7;
- the production SSE capacity test in Phase 7.

Paid provider calls remain opt-in and excluded from default CI.

## Acceptance criteria

- One FabricAssist v1 API serves web, iOS, and Android through the shared Expo
  codebase.
- `/api/v1/graphql` exposes one query-only Strawberry schema with no mutation
  root.
- Apollo Client with `InMemoryCache` is the only GraphQL client, and TanStack
  Query remains the REST server-state client.
- Result detail, garment detail/history, and image metadata reads use generated
  GraphQL documents.
- Every write, upload, authentication/session operation, AI command, feedback
  action, identity decision, review action, and deletion uses REST.
- `/api/v1/runs/{id}/events` is the real-time progress/display-event stream.
- Initial/reconnect recovery and every terminal SSE event synchronize canonical
  GraphQL state before persistent UI state is presented.
- Every shared Expo REST write has a centralized, typed, tested cache-effect or
  explicit justified no-effect declaration.
- Apollo cache state cannot cross users or tenants.
- REST controllers and GraphQL resolvers are thin adapters over shared
  application services/queries for migrated surfaces.
- Request-scoped DataLoaders never share cache across requests or tenants.
- All retained ordered GraphQL connections use opaque keyset pagination.
- Tenant/user ownership, archive/deletion state, validator release state, and
  product-evidence provenance are consistent across transports.
- No cross-tenant existence, object key, image bytes, complete presigned URL, raw
  provider payload, rejected proposal, credential, or stack trace leaks through
  the v1 API or logs.
- Sanitized error codes and correlation IDs work across REST, GraphQL, and SSE.
- Result canonical reads use one GraphQL request rather than the previous
  multi-REST-read sequence.
- Normal metadata requests meet the required 500 ms p95 under expected and
  tested SSE load.
- SQL query counts remain independent of result/history page size.
- `make graphql` and `make check-graphql-drift` pass; the breaking check passes
  normally or through the exact hash-bound ADR-017 mutation-removal approval.
- Backend/frontend tests, web E2E, Android smoke, iOS smoke, and production
  capacity validation pass or the task remains incomplete.
- Existing REST reads remain supported until a separate retirement task changes
  that decision.

## Explicitly out of scope

- GraphQL mutations, subscriptions, federation, or a gateway.
- Moving authentication, uploads, files, AI commands, feedback, identity
  decisions, service events, review actions, or deletion away from REST.
- Replacing SSE with GraphQL subscriptions or WebSockets.
- Exposing image bytes or object-storage keys through GraphQL.
- A second API service or second business source of truth.
- Persistent Apollo cache storage.
- Rewriting unrelated application/route ORM debt.
- Changing deterministic validation, provider selection, retention, product
  provenance, or garment-identity semantics.
- Offset pagination.
- Retiring REST read endpoints.
- Adding indexes without measured query-plan evidence.

## Completion record

At completion, record:

- commit and pull-request references;
- exact mutation-root removal and approved breaking-change manifest;
- migrated screens and generated document names;
- REST-write cache-registry inventory and test evidence;
- shared application services/query ports and infrastructure adapters;
- removed resolver/controller ORM access;
- baseline versus final request count, p95 latency, SQL query count, DataLoader
  batch count, bundle size, and mobile memory;
- exact CI and local validation results;
- web, iOS, Android, SSE reconnect/polling, and production capacity evidence;
- migrations/indexes, configuration changes, rollback evidence, and remaining
  work.

Update the parent mixed GraphQL/REST/SSE task after each completed phase. Do not
archive it until its remaining production rollout requirements are complete.
