# Future task: migrate customer garment history reads to GraphQL

**Status:** Implemented locally  
**Created:** 2026-07-31  
**Suggested branch:** `feat/graphql-garment-history`  
**Related:** [ADR-016](../adr/016-mixed-graphql-rest-sse-api.md),
[Mixed GraphQL/REST/SSE task](mixed-graphql-rest-sse-api.md),
[requirements](../requirements.md), [architecture](../architecture.md)

## Goal

Move the customer garment-history **read** from REST to a typed, paginated,
tenant-safe GraphQL query without changing the screen's visible information,
security properties, or newest-analysis-first ordering.

The task implements one small migration slice only. It does **not** retire REST
history routes, replace uploads or AI commands, or move deletion mutations to
GraphQL.

## Why this task exists

ADR-016 selects GraphQL for canonical frontend reads and simple metadata
mutations, REST for uploads and AI-run commands, and SSE for run progress.
The mixed-transport implementation task records that customer history remains
on REST until a feature-equivalent GraphQL document and UI behaviour exist.

`frontend/apps/client/src/app/(customer)/history.tsx` currently calls
`GET /api/v1/garments`. Its rendered cards require fields not exposed by the
current GraphQL `GarmentType`:

- garment ID and user-visible identifiers;
- a short-lived, owner-authorized thumbnail URL when an image exists;
- `last_analysis_at`;
- `analysed_before` and `cleaned_before` as separate facts.

The REST endpoint already presents completed history with these facts, and
sorts it by latest analysis first, with garments that have no analysis last.
The existing GraphQL `garments` resolver orders by UUID, so it must not be used
as the history screen's source unchanged.

## Requirements and invariants

- Preserve garment-centred history: the top-level customer history lists physical
  garments; individual analyses remain inside the garment-detail screen.
- Return only the current user's non-archived garments for their tenant. A query
  must not reveal the existence of another tenant's/user's garment.
- Preserve `analysed_before` versus `cleaned_before`; only a `completed` service
  event may make `cleaned_before` true.
- Sort by `last_analysis_at DESC NULLS LAST`, with a deterministic UUID tie-breaker.
- Use opaque cursor pagination. Do not treat a UUID as a cursor when the sort key
  contains a timestamp.
- Thumbnail URLs must remain short-lived, private, owner-authorized presigned
  GET URLs. Never expose object keys, permanent public URLs, or image bytes.
- Keep the GraphQL schema source generated from Strawberry and keep generated
  frontend GraphQL artifacts deterministic. Do not hand-edit generated files.
- Keep REST `GET /api/v1/garments` working during this migration. Keep deletion
  on REST in this slice; its GraphQL mutation migration is separate work.
- Reuse application/query logic where practical. Do not duplicate tenant,
  archive, service-event, or image-selection rules across REST and GraphQL.
- Do not add Apollo, a new service, database triggers, or a migration unless a
  measured query plan proves a new index is necessary.

## Proposed API contract

Add a dedicated, additive GraphQL query rather than changing the current
`garments(first, after: UUID)` argument. The current query's UUID cursor cannot
correctly represent the required composite history order; changing it would be
a breaking schema change.

```graphql
type Query {
  garmentHistory(first: Int! = 20, after: String): GarmentHistoryConnection!
}

type GarmentHistoryConnection {
  items: [GarmentHistoryItem!]!
  pageInfo: PageInfo!
}

type GarmentHistoryItem {
  id: UUID!
  identifiers: [String!]!
  thumbnailUrl: String
  lastAnalysisAt: DateTime
  analysedBefore: Boolean!
  cleanedBefore: Boolean!
}
```

`after` is an opaque, URL-safe cursor encoding the final item’s normalized
analysis timestamp (or an explicit no-analysis marker) plus the UUID tie-breaker.
It is implementation detail, not a garment ID. Invalid, malformed, or
out-of-scope cursors must produce the existing sanitized GraphQL request error;
they must not leak data.

`PageInfo.nextCursor` remains `null` when no further page exists. The UI need
not implement an infinite-scroll design in this slice, but its query must retain
and be tested with the cursor contract so pagination can be enabled without a
transport redesign.

## Implementation plan

### 1. Establish a shared history projection

- Inspect and extract the read-only projection now built in
  `backend/src/fabricassist/api/routes/garments.py:response_for` and
  `list_garments`.
- Place the projection/query in an application service or repository query that
  both the REST route and GraphQL resolver can call. It must receive explicit
  tenant/user scope and the object-storage port.
- Load identifiers, latest active analysis revision, completed service-event
  state, and thumbnail image without per-garment query amplification. Use
  batched SQL/subqueries or a DataLoader-backed approach, and verify query
  counts in tests.
- Preserve REST behaviour exactly while replacing its internal implementation
  with the shared projection where safe.

### 2. Add the GraphQL history schema and resolver

- Add Strawberry `GarmentHistoryItem` and `GarmentHistoryConnection` types plus
  the `garment_history` resolver in
  `backend/src/fabricassist/api/graphql_schema.py`.
- Extend `GraphQLContext`/composition only as needed to inject the existing
  `ObjectStorage` port; do not construct provider clients in resolvers.
- Authorize through the existing authenticated GraphQL context, filter archived
  garments, and return not-found/sanitized errors consistently with current
  GraphQL behavior.
- Implement keyset pagination for `(last_analysis_at, garment_id)` and avoid
  offset pagination. Define an explicit `NULLS LAST` cursor branch for garments
  that have never been analysed.
- Use the same most-recent eligible image rule as the REST response before
  presigning a thumbnail. Do not log a presigned URL.

### 3. Generate and consume typed frontend documents

- Add `GarmentHistory` as a colocated operation, for example:
  `frontend/apps/client/src/app/(customer)/history.operations.graphql`.
  Replace or rename the existing unused `ScanHistory` operation so no misleading
  stale operation remains.
- Include exactly the fields required by the current cards; add `pageInfo` for
  cursor correctness.
- Run `make graphql` to regenerate
  `docs/api/graphql/schema.graphql` and
  `frontend/packages/api-client/src/graphql/generated/`.
- Update `history.tsx` to obtain `graphql` from `useSession`, call
  `GarmentHistoryDocument` through the shared executor, and retain TanStack
  Query loading/error/empty states and the `customer-history` cache key.
- Continue to call `deleteGarmentApiV1GarmentsGarmentIdDelete` for deletion.
  On success invalidate the GraphQL history cache and any affected garment/scan
  caches. Do not implement optimistic deletion unless it has its own tested
  design.

### 4. Tests

Backend:

- Unit tests for cursor encode/decode, invalid cursors, ordering, page boundaries,
  null `last_analysis_at`, UUID tie-breaks, and no duplicate/missing garments
  across pages.
- GraphQL tests for authentication, tenant/user isolation, archived-garment
  exclusion, result shape, thumbnail privacy, and the strict separation between
  analysed and completed-cleaned state.
- Query-count/N+1 coverage for a multi-garment page.
- Regression coverage proving the GraphQL history order matches the REST order:
  newest analysed first; never-analysed last.

Frontend:

- Update the garment-history component test to mock `graphql` and verify the
  typed history response renders the existing identifier, date, thumbnail
  fallback, analysed-before, and cleaned-before states.
- Verify the deletion confirmation still uses REST and invalidates the GraphQL
  history query after success.
- Add executor coverage only if existing authenticated GraphQL transport tests
  do not already cover the required request/error path.

### 5. Documentation and generated-contract checks

- Regenerate checked-in SDL and GraphQL generated files; never edit either by
  hand.
- Update the implementation-progress section in
  `docs/feature-tasks/mixed-graphql-rest-sse-api.md` to say that the customer
  garment-history read is GraphQL-backed, while deletion remains REST.
- Add a concise changelog entry only if this task is released to users.
- Do not modify OpenAPI artifacts merely because a GraphQL read is added; REST
  remains documented and supported.

## Validation commands

Run the applicable commands from the repository root and report only actual
results:

```bash
make graphql
make check-graphql-drift
make check-graphql-breaking
cd backend && uv run pytest tests/unit/test_graphql_schema.py
cd backend && uv run pytest tests/unit
pnpm --dir frontend test -- garment-history-deletion
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build:web
make lint
```

Run broader `make test`/`make check` when the working tree and local services
allow it. If any integration test needs PostgreSQL/object storage, use the
repository's normal Compose workflow; never use paid providers by default.

## Acceptance criteria

- Customer history fetches its garment cards from `/api/v1/graphql`, using the
  generated `GarmentHistoryDocument` and the shared authenticated executor.
- The screen shows exactly the same visible history facts and thumbnail behavior
  as before the migration.
- The returned order is latest analysis first and never-analysed garments last,
  including across cursor pages.
- The GraphQL resolver enforces tenant/user ownership and hides archived garments.
- Thumbnail URLs are still short-lived and private; object keys and image bytes
  never appear in GraphQL responses or logs.
- `analysed_before` and `cleaned_before` remain semantically distinct.
- Garment deletion remains functional via REST and refreshes GraphQL-backed
  history afterward.
- SDL/codegen artifacts are synchronized, all relevant tests pass, and no
  unrelated transport migration is included.

## Explicitly out of scope

- Replacing REST upload, image-preview, analysis/run, product-lookup, or
  identity-command endpoints.
- Retiring `GET /api/v1/garments`.
- Moving `deleteGarment` or other metadata mutations to GraphQL.
- Migrating garment-detail history, scan history, or operator views.
- Apollo, subscriptions/WebSockets, a dedicated GraphQL service, persistent
  GraphQL caches, or changes to care-validation behavior.

## Risks and mitigations

| Risk                                                                     | Mitigation                                                                                            |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Different GraphQL order changes the user-visible “newest first” behavior | Use a timestamp-plus-UUID keyset cursor and a direct REST/GraphQL ordering regression test.           |
| N+1 queries from identifiers, service events, images, and revisions      | Use a shared batched projection and query-count coverage before merging.                              |
| Presigned thumbnail URLs accidentally disclose storage internals         | Generate them only from owner-scoped server data; return no object key and never log the full URL.    |
| A schema change disrupts current GraphQL callers                         | Add an additive `garmentHistory` field and run `make check-graphql-breaking`.                         |
| Deletion leaves stale cards in the GraphQL cache                         | Invalidate the exact history and related garment/scan keys after the existing REST mutation succeeds. |

## Completion record

- **Implementation:** Added the shared tenant-scoped garment-history projection,
  opaque timestamp-plus-UUID cursors, additive `garmentHistory` GraphQL query,
  private thumbnail presigning, generated typed frontend operation, and history
  screen migration. Garment deletion remains REST and invalidates the GraphQL
  history cache.
- **Database/index evidence:** No migration or new index was necessary. The
  projection uses four bounded queries per page (garments/revision, identifiers,
  service events, and thumbnails) rather than per-garment related-data queries.
- **Validation:** `cd backend && uv run pytest tests/unit` — 174 passed;
  focused Ruff checks passed; `pnpm --dir frontend test --
  garment-history-deletion.test.tsx` — 1 passed; frontend lint and typecheck
  passed; `pnpm --dir frontend build:web` passed; `make graphql` passed.
  `make check-graphql-drift` regenerated artifacts but exits non-zero in this
  uncommitted working tree because the expected SDL/generated changes differ
  from HEAD; run it again after committing the generated artifacts.
- **Deliberate deviations:** The existing REST garment-list implementation
  remains available and keeps its response shape; only the customer history
  screen's read transport changed. The parent mixed API task remains active.

The parent mixed API task must not be archived until its other phases and
rollout evidence are complete.
