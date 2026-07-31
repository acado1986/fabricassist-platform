# Mixed GraphQL, REST, and SSE API

**Status:** In progress
**Started:** 2026-07-31
**Executor:** GPT-5.6 Luna (high reasoning)
**Plan branch:** `docs/mixed-graphql-rest-sse-api-plan`
**Implementation branch:** `feat/mixed-graphql-rest-sse-api` (create from updated `main` after this task is merged)

> **Superseded implementation guidance:** ADR-017 and
> [`storefront-graphql-read-migration.md`](storefront-graphql-read-migration.md)
> supersede this task's allowance for GraphQL metadata mutations, its prohibition
> on a normalized GraphQL client, and its REST-first reconnect recovery. For all
> remaining storefront work, GraphQL is query-only, every write remains REST,
> Apollo Client supplies the shared normalized cache, and GraphQL is the
> canonical resynchronization point before SSE reconnect and after terminal
> events. The historical phases below remain useful implementation evidence but
> must not override ADR-017.

Phase 2 result-read work is now implemented in the active migration branch:
`result.tsx` uses the generated `scanResult` Apollo operation as its canonical
read, while identity decisions, feedback, deletion, and run commands remain
REST writes. `RunStreamLifecycle` awaits a network-only GraphQL recovery before
initial/reconnect SSE opens and after completed, failed, or cancelled terminal
events; bounded foreground GraphQL polling is the fallback when SSE is
unavailable. The phase remains subject to its mobile smoke and query-count
acceptance checks.

Phase 3 and Phase 4 are also implemented in the active branch: garment detail
and paginated scan history use the generated `GarmentDetail` Apollo operation,
while image metadata uses `ScanImageMetadata`; thumbnail preview/download
continues through REST file operations and GraphQL does not expose presigned
URLs or object keys. The shared SQLAlchemy query adapter is used by the
compatible REST garment reads and GraphQL reads.

Phase 5 records a no-migration decision: session/authentication and the
opportunistic bootstrap request remain REST because no measured startup
waterfall currently exists for a GraphQL bootstrap composite to remove.

Phase 6 hardening converted the retained `scans`, `garments`, and `messages`
GraphQL connections to versioned opaque keyset cursors. The intentional three
argument-type changes are bound to ADR-018 and an exact SDL approval manifest;
all other breaking changes remain fail-closed.

Phase 7 local release checks and a bounded local metadata load smoke passed.
The GraphQL implementation and follow-up history synchronization/deletion fixes
are prepared for production release `v1.3.5`, but production
SSE capacity/starvation validation remains deferred until the deployed API URL
and protected smoke credentials are supplied. Android and iOS smoke evidence is
also pending the required device runners.

**Created:** 2026-07-31
**Preparation:** `AGENTS.md`, `docs/requirements.md`, `docs/architecture.md`,
`docs/environment.md`, `docs/database.md`, `docs/production/`,
`docs/runbooks/`, current REST routes, persistence models/migrations, worker,
Expo client, generated OpenAPI client, tests, and deployment configuration.

## 1. Executive summary

Evolve the existing modular FastAPI monolith incrementally. GraphQL supplies
read-only composite application reads; REST remains the boundary for every
write, direct-to-private-object-storage image upload, authentication action, and
long-running AI command; SSE supplies ordered, reconnectable run progress and
safe assistant-message display. PostgreSQL remains authoritative; Valkey is
used only for rate limits, connection/concurrency limits, short-lived locks,
retry counters, and optional hot cache.

This is not a rewrite, does not add LangGraph, does not introduce a separate
service, and retains the current `/api/v1` REST surface while clients migrate.
The existing resource vocabulary is preserved: a user-facing "session" maps to
the existing **scan** and (where applicable) **garment**, rather than creating a
parallel `session` model.

## 2. Current-state assessment

FabricAssist already works as a FastAPI modular monolith with a separate worker.
The task is an additive transport evolution: preserve the current REST command
and direct-upload flow, introduce a read-oriented GraphQL boundary, and make
already-persisted asynchronous progress available through SSE. It is a
cross-cutting architecture change because the active requirements are REST/JSON
and the architecture currently defers conversation streaming.

## 3. Confirmed repository findings

- The backend is FastAPI under `backend/src/fabricassist/api/`; current public
  APIs are REST under `/api/v1` and generated OpenAPI is the existing REST
  client contract.
- `scans.py` implements draft scans, image upload instructions, upload
  completion, analysis start, detail/history/result, feedback, and deletion.
  Upload bytes go directly to private S3-compatible storage via presigned PUT;
  the API does not proxy multipart bytes.
- A scan has configurable image count (MVP default eight), uploaded-image
  metadata, size/decode/dimension validation, and durable PostgreSQL state.
- Analysis and chat are durable, asynchronous PostgreSQL-outbox workflows
  dispatched through QStash in hosted production or Celery locally. Existing
  `AnalysisJobOperation` records are stage operations, not a client-visible run
  lifecycle.
- Gemini adapters return complete schema-validated results. Conversation output
  is validated before its assistant message is persisted; it does not expose a
  safe raw-token stream.
- The Expo client uses TanStack Query and a generated Hey API OpenAPI client.
  `authenticated.ts` already centralizes bearer headers, correlation IDs, and a
  single refresh on HTTP 401. The ADR-017 cutover uses Apollo Client for
  GraphQL reads and the generated client for REST writes/reads; the generated
  client also contains a low-level SSE frame parser.
- Hosted production uses Cloudflare Pages, Render API, Neon PostgreSQL, private
  R2, QStash, and TLS Valkey. Repository configuration does not establish that
  the selected Render service/proxy tolerates production SSE; this requires a
  deployed validation before rollout.

## 4. Assumptions

1. The selected hosting tier can be validated for a short-lived, reconnectable
   SSE endpoint; polling remains available if not.
2. Direct storage upload remains the supported upload transport. "Multipart" in
   this task means the existing one-image-at-a-time, presigned-object PUT
   workflow; no API multipart proxy is added because it violates ADR-007 and
   adds avoidable server bandwidth/cost. Storage multipart upload is not needed
   at the 12 MB configured limit.
3. A run is an immutable client-command lifecycle that can contain existing
   analysis or conversation work; it is not a replacement for analysis
   revisions, model runs, messages, feedback, or results.

## 5. Decisions

- Add Strawberry GraphQL to the same FastAPI application at `/api/v1/graphql`.
  Keep FastAPI OpenAPI and the generated REST client for REST endpoints.
- Use GraphQL Code Generator's `@graphql-codegen/client-preset`, generated typed
  documents, and Apollo Client with `InMemoryCache` across web, iOS, and
  Android. Keep TanStack Query for generated REST operations and reuse the
  existing authenticated refresh-once abstraction.
- Emit `message.delta` only by deterministic chunking **after** the full
  assistant message passes validation and is committed. Pre-validation updates
  contain non-content progress only. This preserves the validator gate.
- Persist terminal/lifecycle events and replayable message chunks in PostgreSQL.
  Heartbeats and connection counters remain transient; Redis/Valkey is never
  an event log.
- Retain existing names: GraphQL types/operations use `Scan`, `Garment`,
  `AnalysisRevision`, `ConversationMessage`, and `AiRun`, not a new `Session`
  aggregate.

## 6. Out-of-scope items

LangGraph, raw provider-token streaming, subscriptions/WebSockets, a new
microservice, replacing the worker/queue, direct database access from Expo,
public image URLs, persistent Apollo-cache storage, and deletion of legacy REST
reads before a separate approved retirement task.

## 7. Target architecture

```text
Expo Android / iOS / web
  ├─ GraphQL: read-only composite application reads
  ├─ REST: every write, auth action, upload, and AI-run command
  └─ fetch-based SSE: ephemeral run progress and safe display chunks
                         ↓
FastAPI application
  ├─ GraphQL Router / REST routes / SSE route
  └─ application use cases (one source of business behavior)
       ├─ ScanService / GarmentService / ConversationService
       ├─ UploadService / AnalysisRunService / UsageService
       └─ repositories, Gemini ports, object storage, Valkey helpers
                         ↓
PostgreSQL (source of truth), R2/S3 (private objects), Valkey (transient)
```

## 8. Proposed backend structure and shared application layer

Routes and resolvers may adapt transport DTOs only. Ownership, idempotency,
validation, state transitions, queries, and transaction boundaries belong in
application services/repositories and are reused by REST, GraphQL, workers,
and recovery loops.

## 9. Proposed frontend structure

The current Expo app remains a single universal application. Put the Apollo
client factory, scalar codecs, generated typed documents, REST run/upload
helpers, and SSE parser in `frontend/packages/api-client`; keep Apollo query
operations and TanStack Query hooks next to their owning route or feature. Use
tiny `.native`/`.web` lifecycle or binary-upload adapters only where platform
behavior actually differs.

## 10. GraphQL schema plan and client typing/runtime

### Server surface

Initial schema types include `CurrentUser`, `Scan`, `ScanConnection`,
`Garment`, `GarmentConnection`, `ScanImageMetadata`, `AnalysisRevision`,
`CareResult`, `ConversationMessage`, `ConversationMessageConnection`, `AiRun`,
`UsageSummary`, `Feedback`, cursor `PageInfo`, and stable string-backed enums.
Image metadata never exposes object keys or permanent URLs; REST preview remains
on demand.

Initial queries:

```text
currentUser
scans(first, after, status)
scan(id)
garments(first, after)
garment(id)
messages(scanId, first, after)
analysisRevision(id)
usage
```

`scans`/`scan` are the repository-specific mapping for the requested conceptual
session list/detail/history. `usage` is administrator-only and aggregates the
existing durable `model_runs`; it does not introduce a duplicate usage table.

The initial GraphQL mutation fields are legacy implementation artifacts.
ADR-017 requires their removal after confirming there is no supported GraphQL
mutation caller; every equivalent operation remains REST.

Every resolver receives the same authenticated FastAPI context as REST, verifies
current user/tenant/role, calls a shared service, and converts expected domain
failures to stable sanitized GraphQL extensions. Never reveal object existence
across tenants. Use DataLoaders/batched repository calls, cursor pagination,
maximum depth, aliases/token limits, a weighted custom complexity validator,
production introspection disabled, and opaque production error messages with a
correlation ID.

### Typed frontend contract

- Checked-in SDL: `docs/api/graphql/schema.graphql`, exported deterministically
  from Strawberry.
- Configuration: `frontend/codegen.ts`.
- Generated artifacts: `frontend/packages/api-client/src/graphql/generated/`.
- Shared scalar codecs: `frontend/packages/api-client/src/graphql/scalars.ts`.
- Runtime client: `frontend/packages/api-client/src/graphql/apollo.ts`.
- Reusable fragments: `frontend/apps/client/src/graphql/fragments/*.graphql`.
- Colocated operations: `*.operations.graphql` beside the route/screen/feature
  that owns them. This is the least disruptive convention for the current
  route-oriented app.

Use `@graphql-codegen/client-preset` with AST `DocumentNode` output, fragment
masking, `strictScalars: true`, and `defaultScalarType: "never"`. Map `UUID`,
`DateTime`, `Decimal`, and JSON explicitly. Validate outgoing custom scalars and
input builders through Zod; server scalar parsing/serialization is strict.
Generated documents infer result, input, and variable types. Handwritten
GraphQL `*Response`, `*Variables`, or `*Input` interfaces are prohibited;
derived screen-only shapes must be named `*ViewModel` and come from a mapper.

Required scripts/CI targets:

```text
pnpm --dir frontend generate:graphql
pnpm --dir frontend generate:graphql:watch
pnpm --dir frontend check:graphql
make graphql
make check-graphql-drift
make check-graphql-breaking
```

`make graphql` exports SDL then runs codegen. Drift regenerates and requires a
clean diff; breaking detection compares the checked-in SDL against the merge
base with a pinned GraphQL Inspector command. TypeScript typechecking includes
the generated directory.

Apollo reuses the authenticated client’s base URL, bearer header, correlation
ID, one-token-refresh behavior, error envelope conventions, and `AbortSignal`.
It classifies HTTP/network/GraphQL errors and remains platform neutral. Apollo's
memory-only `InMemoryCache` owns canonical GraphQL data and cursor pagination;
TanStack Query remains for generated REST operations. REST command responses are
acknowledgements, not a second canonical cache. SSE progress is local ephemeral
run state only. On `run.completed`, perform a network-only canonical GraphQL
query for the exact scan/garment/messages/usage affected; do not treat streamed
text as permanent canonical data.

## 11. REST endpoint plan

Preserve existing route conventions:

```text
POST   /api/v1/scans/{scan_id}/images
DELETE /api/v1/scans/{scan_id}/images/{image_id}
POST   /api/v1/scans/{scan_id}/uploads/complete
POST   /api/v1/scans/{scan_id}/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/cancel
POST   /api/v1/runs/{run_id}/retry
GET    /api/v1/runs/{run_id}/events
GET    /api/v1/health/live
GET    /api/v1/health/ready
```

Existing `POST /analyse` and `POST /messages` remain compatible wrappers while
migration is active and return/include a `run_id` when asynchronous work starts.
Only shared `AnalysisRunService` creates/cancels/retries runs.

Upload instructions must retain one-to-eight completed images, server-generated
safe IDs/keys, role/order/metadata, MIME/type/size/decode/pixel limits, direct
object verification, content SHA-256 during completion, same-scan duplicate
rejection, ownership checks, idempotency, and durable abandoned/failed upload
cleanup. Never log bytes, raw object URLs, or full object keys. A retry does not
reuse an unsafe/failed image.

A run command validates scan ownership, selected completed image IDs, optional
user message, idempotency key, and allowable state; creates a durable pending
run plus identifier-only outbox work transactionally; and returns `202` with its
run state. Workers persist checkpoints/progress, bounded timeouts, categorized
failure, and cancellation intent. Cancellation is cooperative: if Gemini cannot
be interrupted, discard its result if cancellation wins. Retry creates an
immutable child run with its own idempotency scope, never mutates a terminal run.
The assistant message/result is committed before completion is published.

## 12. SSE protocol and event contract

Endpoint: `GET /api/v1/runs/{run_id}/events` with `Accept: text/event-stream`.
Use a fetch-based SSE client so Android/iOS/web can send `Authorization`; browser
`EventSource` cannot add the existing bearer header.

Every durable event has this envelope:

```json
{
  "schema_version": 1,
  "event_id": "UUID",
  "run_id": "UUID",
  "sequence": 4,
  "timestamp": "2026-07-31T12:00:00Z",
  "data": {}
}
```

Event names: `run.created`, `run.started`, `run.progress`, `message.delta`,
`message.completed`, `run.completed`, `run.failed`, `run.cancelled`, and
`heartbeat`. `event.id` is the monotonic run sequence; `event` is the name;
`data` is the envelope. The event table has unique `(run_id, sequence)` and UUID
`event_id`; clients keep last sequence/event ID and ignore duplicate/lower
sequences.

Authenticate/authorize before opening; check connection and run rate limits;
poll committed PostgreSQL events with short transactions; send heartbeat at a
bounded interval; remove resources on disconnect/cancellation; and close on
terminal event or before access-token expiry. Reconnect uses `Last-Event-ID`
and exponential backoff with jitter. If event retention has expired or the
server restarted, return a typed cursor-expired response and recover with
`GET /runs/{id}` plus the typed GraphQL scan/message query. The client aborts on
background, reconnects only while foregrounded, and falls back to bounded REST
status polling when streaming is unavailable. CORS permits the deployed Expo
origins, `Authorization`, `Last-Event-ID`, and event-stream response headers.

## 13. Database changes

Add one forward-only Alembic revision for `ai_runs`, `ai_run_images`, and
`ai_run_events`; add nullable `run_id` references to the existing job operation
and conversation message records; add `display_name`/`archived_at` only if not
already present on garments. Reuse existing scan images, analysis revisions,
care results, model runs, conversation messages, feedback, and retention jobs.
Persist replayable lifecycle/chunks/terminal events; heartbeat and Valkey state
are transient. Apply tenant/user foreign keys, run/idempotency/parent-run/check
constraints, indexes for owner/status/created time and event sequence, and a
retention cleanup policy. Test upgrade/downgrade from current head.

## 14. Authentication and authorization

Use shared authentication/authorization for REST, GraphQL, and SSE; explicit
object-level checks; signed private storage operations; upload/rate/concurrency
limits; CSRF protections for cookie-authenticated web mutations; token-expiry
handling for streams; sanitized errors; CORS allowlist; prompt-data delimiting;
and quota/concurrency controls around Gemini. Logs/metrics/traces include safe
correlation, tenant/user (when permitted), scan/run IDs, durations, provider
latency, stream connection/disconnect/retry counts, operation names, upload size,
and error categories—never tokens, raw images, presigned URLs, or complete
private conversation content.

## 15. Caching strategy

Use PostgreSQL for durable state. Cache only short-lived query/recovery metadata
in Valkey; a Valkey outage must not lose results or prevent later REST/GraphQL
recovery. Validate Render/CDN/proxy buffering/timeouts with a deployed,
authenticated `curl -N`, Expo web, Android, and iOS smoke; retain polling if the
chosen tier cannot meet the contract.

## 16. Error handling

REST retains the stable error envelope. GraphQL exposes typed expected error codes in extensions with a correlation ID and no stack/database/provider text. SSE reports typed terminal failures and does not send secrets or raw provider payloads.

## 17. Retry and recovery strategy

Client retries only safe reads/reconnects; commands use idempotency keys and must not be blindly retried after an indeterminate response. Provider network timeouts use existing bounded worker retry policy; validation, ownership, invalid-image, and cancellation outcomes are not blind retried. Database failure means no completion event; event creation and final persistence share a transaction. Redis/Valkey failure degrades stream limits/cache only according to fail-closed security settings and never becomes the data source.

## 18. Cross-platform Expo considerations

The shared fetch executor and SSE parser must use Expo-supported `expo/fetch` streaming behavior and standard `AbortController`, not browser-only `EventSource`. Android, iOS, and web share framing, cursor, duplicate suppression, retry, and canonical-refetch code; `AppState` foreground/background wiring stays in a small platform adapter. REST direct uploads remain behind the existing native/web binary-upload adapters.

## 19. Deployment considerations

GraphQL, REST, and SSE initially run in the same FastAPI container. Keep the existing API/worker split, Neon, R2, QStash, and Valkey topology. The implementation phase must verify Render hosting behavior for SSE rather than assume it.

## 20. Security controls

The controls in Sections 11–17 are mandatory: shared auth, tenant ownership, strict upload validation, rate/concurrency limits, GraphQL complexity limits, CORS/CSRF protections, token expiry handling, private signed storage operations, sanitized errors, prompt-data boundaries, and Gemini quota abuse controls.

## 21. Observability

Record correlation, scan, run, and safe tenant/user identifiers; run/Gemini/GraphQL durations; GraphQL operation names; stream count, disconnect, retry, and failure categories; and upload size. Redact tokens, raw images, object URLs, provider payloads, and complete sensitive conversations by default.

## 22. Testing strategy

Backend: resolver unit/integration/auth/object-access/N+1/limits/introspection
coverage; REST run/idempotency/cancel/retry/status coverage; direct-upload
one-through-eight, invalid type/size/pixels/hash/duplicate/ownership/cleanup
coverage; event formatter/order/replay/cursor expiry/disconnect/heartbeat tests;
worker timeout/failure/cancel/database/Valkey/auth-expiry tests; migration tests;
and redaction/metrics tests.

Frontend: generated-document typecheck, scalar validation, executor refresh and
abort, typed query hooks/cursors/cache invalidation, REST upload/run client,
SSE parser partial/multiple chunks/dedup/retry/background/foreground/fallback,
and Android/iOS/web adapter smoke tests. E2E proves create scan → direct upload
→ start run → progress → validated assistant display → persisted result →
GraphQL canonical scan/message read. Default tests use mock providers/local
services only.

## 23. Backward-compatible migration strategy

Follow the additive order below: document the change; extract shared services;
add durable runs; retain existing REST routes; add SSE and its GraphQL recovery
fallback; add GraphQL read operations; migrate screens; add deterministic REST
write cache effects; and validate production behavior. Do not remove REST reads,
direct uploads, or REST commands in this task.

## 24. Ordered implementation phases

### Phase 1 — Baseline, ADR, and contract alignment

- **Goal:** Make the architectural decision explicit before code.
- **Likely files:** this task; new ADR; requirements, architecture, environment,
  threat model, production/runbook docs; Makefile/CI plan.
- **Database/backend/frontend:** none beyond documentary contracts.
- **Tests/commands:** `git diff --check`, link checks, `make lint` where docs do
  not alter tooling.
- **Acceptance:** REST-only/deferred-streaming statements are replaced with the
  bounded mixed-API decision; direct uploads and safety gates remain explicit.
- **Dependencies:** none. **Rollback:** revert docs only.

### Phase 2 — Shared application use cases

- **Goal:** Extract reusable scan/garment/upload/conversation/run commands and
  queries before adding another transport.
- **Likely files:** `application/`, route adapters, repositories, unit tests.
- **Database:** none unless interfaces expose needed query indexes.
- **Backend/frontend:** routes delegate; no client behavior change.
- **Tests/commands:** route compatibility + service tests; `make lint`, focused
  pytest. **Acceptance:** REST behavior/API snapshot remains compatible and no
  resolver-specific business logic is required. **Dependencies:** Phase 1.
  **Rollback:** keep route adapter on prior function until extraction validated.

### Phase 3 — Durable AI runs and events

- **Goal:** Add authoritative client-visible run lifecycle.
- **Likely files:** models/repositories, Alembic, run service, jobs/worker,
  REST schemas, tests.
- **Database:** `ai_runs`, `ai_run_images`, `ai_run_events`, references/indexes.
- **Backend/frontend:** run creation/status behind existing command wrappers;
  no UI dependency yet.
- **Tests/commands:** migration previous-head/empty DB, idempotency/state/cancel
  tests, `make test-migrations`, focused pytest.
- **Acceptance:** each command creates one durable run, retry creates child run,
  terminal result persists before durable terminal event. **Dependencies:** 2.
  **Rollback:** additive schema + retain old commands.

### Phase 4 — REST command compatibility and upload hardening

- **Goal:** Expose run REST endpoints and complete direct-upload invariants.
- **Likely files:** scans/runs routes/schemas, storage verification, OpenAPI,
  generated REST client, Expo upload hooks/tests.
- **Database:** optional hash/cleanup metadata migration only if absent.
- **Tests/commands:** multipart-instruction/direct-PUT completion tests,
  1..8, hash/duplicate/ownership/idempotency tests; `make openapi`,
  `make check-openapi-drift`.
- **Acceptance:** legacy `/analyse`/messages remain functional and new run
  endpoints are idempotent/authorized. **Dependencies:** 3. **Rollback:** route
  aliases continue delegating shared service.

### Phase 5 — SSE backend

- **Goal:** Add safe reconnectable run event stream.
- **Likely files:** SSE route/formatter, run-event repository, limits/settings,
  metrics/CORS, worker event calls, backend tests.
- **Database:** event retention/index migration if Phase 3 did not include it.
- **Frontend:** none required.
- **Tests/commands:** frame/order/replay/duplicate/heartbeat/disconnect/auth/
  token-expiry/cursor-expiry/Valkey-loss tests; `make lint`, focused pytest.
- **Acceptance:** validated chunks and terminal events replay from PostgreSQL;
  no raw model text leaks. **Dependencies:** 3–4. **Rollback:** clients poll
  run status and stream route is disabled.

### Phase 6 — Universal Expo run/SSE client

- **Goal:** Provide one fetch-based stream client and polling fallback.
- **Likely files:** `packages/api-client`, small platform lifecycle adapter,
  scan/chat screens, Jest tests.
- **Database/backend:** none.
- **Tests/commands:** parser partial/multi-frame/dedup/backoff/abort/app-state
  tests; `pnpm --dir frontend lint typecheck test`, web build.
- **Acceptance:** Android, iOS, and web share stream logic; terminal event only
  drives canonical refetch. **Dependencies:** 5. **Rollback:** feature flag to
  existing polling.

### Phase 7 — Strawberry, SDL, and Codegen foundation

- **Goal:** Add secure GraphQL transport and typed document pipeline without
  migrating UI reads.
- **Likely files:** GraphQL package/router/context/scalars/limits, dependencies,
  `docs/api/graphql/schema.graphql`, `frontend/codegen.ts`, generated output,
  Makefile/CI/tests.
- **Database:** none.
- **Tests/commands:** unauthenticated/limits/introspection/scalar tests,
  `make graphql`, codegen drift/break/typecheck.
- **Acceptance:** GraphQL uses shared auth, production controls, strict scalars,
  deterministic SDL/codegen, and the ADR-017 normalized Apollo client.
  **Dependencies:** 1–2.
  **Rollback:** mount router only behind feature setting/path while REST remains.

### Phase 8 — GraphQL canonical read queries

- **Goal:** Deliver paginated/read-only typed scans, garments, messages,
  revisions, images, usage.
- **Likely files:** schema/resolvers/DataLoaders/query services, colocalized
  documents/hooks/screens, tests.
- **Database:** indexes only if query plans prove need.
- **Tests/commands:** authorization, N+1 query-count, cursor and GraphQL error
  tests; frontend generated query/cache pagination tests.
- **Acceptance:** target history/detail/chat reads are GraphQL-backed and REST
  reads still work. **Dependencies:** 7. **Rollback:** feature flags return
  affected screens to REST query hooks.

### Phase 9 — Superseded by ADR-017

Do not implement the former GraphQL metadata-mutation phase. All metadata,
feedback, identity, archive, deletion, upload, authentication, and command
writes remain REST. The replacement work is the typed REST-write cache-effect
registry and normalized-cache synchronization specified by
`storefront-graphql-read-migration.md`.

### Phase 10 — Observability, security, deployment validation

- **Goal:** Validate operations before defaulting clients to GraphQL/SSE.
- **Likely files:** telemetry/metrics/settings/CORS/runbooks/CI/deployment docs.
- **Database:** optional metric-support indexes only.
- **Tests/commands:** `make security-check`, `make check-production-config`,
  `make check-deployment-workflows`, local load test; explicit opt-in deployed
  SSE smokes.
- **Acceptance:** dashboards/log fields/redaction, failure alerts, proxy timeout
  behavior, and platform fallbacks are documented/proven. **Dependencies:** 5–9.
  **Rollback:** keep polling/REST default.

### Phase 11 — Compatibility completion and controlled legacy-read retirement

- **Goal:** Remove only redundant REST **read** paths after supported clients are
  migrated and telemetry confirms no traffic.
- **Likely files:** route deprecation docs, client flags, OpenAPI/client,
  changelog/runbooks/tests.
- **Database:** none.
- **Tests/commands:** full `make check`, migration/deployment suites, E2E.
- **Acceptance:** REST uploads/commands remain; retirement has measured client
  cutoff and documented rollback window. **Dependencies:** 10. **Rollback:**
  restore compatibility reads during the window.

### Phase 12 — Closeout

- **Goal:** Record implementation evidence and archive this task.
- **Likely files:** task status/archive/indexes, ADR/docs/changelog.
- **Tests/commands:** record all actually-run commands/results.
- **Acceptance:** task includes commit/PR, migration/config evidence, deviations,
  remaining work; move it to `docs/archive/implemented-tasks/`. **Dependencies:**
  all prior phases. **Rollback:** task remains active if a phase is incomplete.

## 25. Acceptance criteria for every phase

Each phase must meet its listed acceptance criterion, run its listed focused validation, preserve preceding behavior, and leave the modular monolith runnable. A phase cannot be marked complete when its required migration, generated artifacts, documentation, test evidence, rollback behavior, or security controls are missing.

## 26. Risks and mitigations

1. **Render/proxy SSE viability:** prove deployed buffering, idle timeout,
   connection limit, restart, CORS, and mobile behavior before enabling by
   default; polling is the mitigation.
2. **Raw AI streaming safety:** never stream provider tokens before deterministic
   validation. The approved display-chunk approach trades token latency for
   correctness.
3. **GraphQL scope creep:** retain all writes on REST and a single backend
   process; Apollo is a normalized read cache, not a second source of truth.
4. **Migration/query performance:** use additive migrations, DataLoaders,
   pagination, query limits, and measured indexes.
5. **Token expiry/reconnects:** close/reconnect safely and recover through a
   network-only canonical GraphQL query before opening a new SSE stream.

## 27. Open questions

6. **Open questions before rollout:** confirm Render production tier/proxy SSE
   behavior and supported access-token lifetime; define durable event retention;
   decide exact GraphQL maximum depth/cost budgets from baseline measurements;
   confirm whether `renameGarment`/archival fields already have a product UX and
   migration; and set tenant-specific Gemini command/concurrency quotas.

## 28. Final recommended implementation order

Execute Phases 1–6 first to make durable REST/SSE behavior safe and backward
compatible; then Phases 7–9 for typed GraphQL and screen migration; finish with
Phases 10–12 only after deployed validation and observability prove rollback and
polling recovery. Each phase is independently verifiable and must leave the
application runnable.

## Implementation progress — 2026-07-31

- **Completed locally:** Phases 1, 3, 4, 5, 6, and 7. The implementation adds
  the ADR/contracts, durable runs/events, REST run controls and compatibility
  wrappers, PostgreSQL-backed SSE, the universal client parser/reconnect path,
  Strawberry, SDL export, and GraphQL Code Generator.
- **Partially completed:** Phases 2, 8, 9, and 10. Customer garment-history
  reads are now GraphQL-backed through the dedicated `garmentHistory` query;
  deletion remains REST. The current shared
  `AnalysisRunService` is used by REST and worker paths; GraphQL now provides
  canonical scan/message/run/revision/image reads and legacy server mutation
  fields that ADR-017 now requires removing. No supported Expo GraphQL mutation
  caller is known. Conversation reads and result recovery use generated typed
  GraphQL documents. Garment-detail/history reads remain on compatible REST
  screens until their feature-equivalent GraphQL documents and UI behaviour are
  migrated. All metadata writes remain REST. SSE metrics are present, but the
  hosted Render/proxy validation has not been run.
- **Deliberately not started:** Phase 11 must wait for client telemetry and a
  rollback window. Phase 12 requires an approved commit/PR plus the complete
  validation evidence; this task remains **In progress** and must not be
  archived yet.
