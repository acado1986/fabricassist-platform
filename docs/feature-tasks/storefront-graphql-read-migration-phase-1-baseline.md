# Storefront GraphQL Read Migration — Phase 1 Baseline

**Captured:** 2026-07-31
**Repository:** `fabricassist-alpha` working tree on `feat/mixed-graphql-rest-sse-api`

This is the Phase 1 baseline record required by
[`storefront-graphql-read-migration.md`](storefront-graphql-read-migration.md).
The working tree already contained uncommitted garment-history GraphQL work
before this phase; those changes were preserved.

## Implementation baseline

Before Phase 1 edits, the repository had:

- a Strawberry schema mounted at `/api/v1/graphql` with a `Mutation` root;
- direct ORM/session/storage access in GraphQL resolvers;
- no request-scoped GraphQL DataLoaders;
- no Apollo client or normalized GraphQL cache;
- no typed REST-write cache-effect registry;
- GraphQL reads in history/chat, while result, garment detail, and image
  metadata reads still used generated REST operations;
- SSE reconnect/terminal behavior without a mandatory canonical GraphQL recovery
  query.

## Baseline validation and measurements

| Measurement | Baseline result | Command/evidence |
| --- | --- | --- |
| SDL generation | Passed | `make graphql` — exit 0 |
| SDL drift | Failed against `HEAD` because pre-existing uncommitted garment-history generated changes were present | `make check-graphql-drift` — exit 1 before Phase 1 edits |
| Breaking schema check | Passed; only three pre-existing additive garment-history changes were reported | `make check-graphql-breaking` — exit 0 |
| GraphQL/backend focused tests | 9 passed | `cd backend && uv run pytest tests/unit/test_graphql_schema.py tests/unit/test_run_events.py` |
| Result-screen REST reads | 3 sequential reads in source (`scan detail`, `identity candidates`, `result detail`) | `frontend/apps/client/src/app/(customer)/result.tsx` |
| GraphQL recovery | Existing direct GraphQL recovery path was present, but it was not Apollo-backed and was not the canonical initial/reconnect/terminal synchronization contract | result-screen SSE effect/source inspection |
| SSE reconnect/terminal canonical sync | Not present in baseline source | result-screen SSE effect/source inspection |
| Authenticated latency, SQL counts, and DataLoader batches | Not captured before this phase: the baseline had no repeatable authenticated benchmark fixture or query instrumentation | Limitation recorded rather than inferred |
| Web bundle size | Not captured before this phase because the baseline build artifact was not present | Limitation recorded rather than inferred |
| Mobile memory | Not captured; no device/emulator runner was available in the baseline environment | Limitation recorded rather than inferred |

The local PostgreSQL, Valkey, MinIO, API, and worker containers were healthy
during implementation (`docker compose ps`). A temporary local registration was
used only after the baseline capture to obtain an authenticated token for
development-only latency smoke measurements; credentials were not committed or
retained in repository files.

## Phase 1 verification measurements

These are post-cutover local smoke measurements, not replacements for the
missing pre-cutover benchmark. They used 30 sequential requests against the
healthy local API and an isolated development account:

| Operation | Median | p95 | Max |
| --- | ---: | ---: | ---: |
| `GET /api/v1/garments` | 7.47 ms | 10.01 ms | 10.70 ms |
| Authenticated GraphQL `garments(first: 20)` | 11.28 ms | 13.72 ms | 14.25 ms |

The exported web artifact measured **2,917,309 bytes** after
`pnpm --dir frontend build:web`. SQL query counts were not instrumented in this
phase; the new batch query adapter is covered by strict typed contracts and the
Phase 1 HTTP/schema tests, while measured SQL/DataLoader telemetry remains a
Phase 6 hardening requirement. Result-screen request count remains three REST
reads until Phase 2; Phase 1 only establishes the canonical Apollo recovery
foundation.

## Measurement policy for later phases

Phase 2 and subsequent phases must add comparable authenticated measurements for
the migrated operation, including request count, p95 latency, SQL query count,
DataLoader batch count, and built web bundle size. Missing platform or deployed
SSE capacity measurements remain explicit blockers for the relevant phase gate.

## Phase 2 measurements

The Phase 2 result composite was measured against the healthy local stack with
the same temporary development account used for the Phase 1 smoke test. Each
sample was a sequential authenticated request; the legacy comparison executed
the existing scan-detail, identity-candidate, and result REST reads for the
same scan.

| Operation | Requests per screen load | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| GraphQL `scanResult` composite | 1 | 16.37 ms | 25.09 ms | 26.94 ms |
| Legacy REST result sequence | 3 | 27.60 ms | 39.82 ms | 48.58 ms |

The result screen now has one generated GraphQL read and no REST status/result/
identity polling path. The Apollo operation uses `network-only` for canonical
initial and recovery reads; bounded foreground GraphQL polling is enabled only
when the transient SSE stream is unavailable. SQL query counts and DataLoader
batch telemetry were not instrumented in this local smoke run, so they remain
an explicit hardening limitation rather than an inferred pass. The rebuilt web
artifact measured **2,918,865 bytes** after the final Phase 2 build.

Android and iOS smoke validation could not run in this Linux environment:
there were no connected Android devices/emulators, and Expo iOS builds require
macOS/Xcode (or a configured EAS runner). These are Phase 2 acceptance blockers.

## Phase 3 and Phase 4 implementation record

Phase 3 now provides a tenant-scoped `garmentDetail` composite with active
analysis/result summaries, identifiers, service events, safe thumbnail image
identifiers, and opaque timestamp-plus-UUID scan-history pagination. The
garment detail screen uses Apollo for metadata and keeps preview URL retrieval
on the existing REST file endpoint. The compatible REST garment reads use the
same storefront query adapter; the application garment-history module contains
no SQLAlchemy or object-storage imports.

Phase 4 now loads image metadata through the generated `ScanImageMetadata`
GraphQL operation. Preview and download URL acquisition remain REST operations;
GraphQL exposes only image ID, role, order, dimensions, and safe metadata.
Focused authenticated GraphQL tests assert that file fields are absent.

The Phase 3/4 local focused gates passed for backend formatting, linting,
typing, GraphQL HTTP/schema tests, frontend formatting, linting, typing, unit
tests, SDL/document generation, and GraphQL breaking/drift checks. Native smoke
checks remain intentionally deferred per the user's explicit instruction to run
them later; they are not being reported as passed.

## Phase 5 decision

No Phase 5 bootstrap migration was made. The shared Expo application has no
measured authenticated startup REST read waterfall that can be removed safely:
session restoration and rotation remain REST, the opportunistic login bootstrap
is a single unauthenticated REST read, and customer screens load their own
feature data. Adding a broad current-user GraphQL query would add coupling
without removing a recorded request. This is the documented no-migration
completion path for Phase 5; startup measurement on native targets remains
deferred with the user's mobile smoke checks.

## Phase 6 hardening record

Retained `scans`, `garments`, and `messages` GraphQL connections now use
versioned opaque timestamp-plus-UUID keyset cursors. Cursor references are
validated through the authenticated tenant/user scope before pagination, and
invalid cursors return a sanitized `INVALID_PAGINATION` error. The exact
argument-type migration is recorded in ADR-018 and approved by the
hash-bound `phase-6-opaque-cursors.approval.json` manifest; unrelated schema
breakage remains fail-closed.

The REST-write registry now has explicit coverage tests for the full shared-app
write inventory, successful 2xx effects, failed writes, and rejected/aborted
writes. Architecture checks also verify that the garment-history application
contract has no SQLAlchemy, persistence, or object-storage imports.

## Phase 7 validation status

Non-production release checks passed, including production settings, Render
workflow/container validation, deployment workflow validation, local migration
integration tests, and a five-second local metadata load smoke at concurrency
8 (`976` requests, `0` failures, `p95 48.3 ms`). The required production
hosting-topology SSE ramp/starvation test was not run because no deployed
production URL and protected smoke credentials were available. It remains a
Phase 7 blocker and is not represented as passed.
