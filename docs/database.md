# Current database baseline and planned garment-intelligence expansion

PostgreSQL is the FabricAssist system of record. Alembic currently has this
applied history:

- `20260721_0001` enables `citext` and `vector` and creates `tenants`, `users`,
  `refresh_sessions`, `scans`, `scan_images`, `idempotency_records`, and
  `ruleset_versions`.
- `20260721_0002` adds refresh rotation and direct-upload lifecycle fields.
- `20260721_0003` adds asynchronous analysis state plus `model_runs`,
  `label_extractions`, `care_results`, and `rendered_answers`.
- `20260722_0004` is the destructive Phases 10–13 cutover: it replaces legacy
  two-photo metadata and extraction/result rows with revision-owned images,
  evidence dossiers, proposals, validation reports, results, and rendered answers.
- `20260722_0005` persists the constrained proposal retry count.
- `20260722_0006` aligns revision-owned rendered answers with the ORM timestamp
  required for auditable result history.
- `20260723_0007` adds physical-garment identity and confirmed service history.
- `20260723_0008` through `20260723_0010` add sourced product lookup records,
  metadata, and explicit invalidation reasons.
- `20260723_0011` adds server-owned contextual conversations and summaries.
- `20260723_0012` adds durable, versioned evidence/plan/render cache records.
- `20260723_0013` adds operator review and deletion lifecycle/outbox records.
- `20260723_0014` upgrades model-run telemetry with request fingerprints,
  latency and token counts, numeric estimated USD cost, and categorized errors.

Never edit those migrations to implement the approved redesign. Phase 10 of
`IMPLEMENTATION_PLAN.md` must add a new revision after current head. The cutover
is intentionally not backward compatible: migrate any data selected for
retention into revision-owned structures and then remove obsolete legacy
constraints/columns/tables instead of supporting dual schemas or code paths.

## Local use

```bash
make up
make migrate
make seed
make migration-test
```

`make migrate` and `make seed` run inside `fabricassist-api` so the service-name
PostgreSQL URL works without exposing credentials in application commands.
`make migration-test` uses isolated PostgreSQL and MinIO Compose services. The
database is exposed on `FABRICASSIST_POSTGRES_TEST_PORT` (default `5433`) and
the private test bucket is initialized on `FABRICASSIST_MINIO_TEST_PORT`
(default `9002`) before the real storage/worker integration test runs.

## Storage constraints

- Baseline primary keys and relationship keys use PostgreSQL UUID columns.
- Timestamp columns are timezone-aware and use PostgreSQL UTC-compatible
  `CURRENT_TIMESTAMP` values.
- Every tenant-owned baseline table has `tenant_id` plus a tenant index.
- `refresh_sessions` stores only `token_hash`, never a raw refresh token.
- `scan_images` stores private object metadata and checksums only; it does not
  store image bytes or presigned URLs.
- `scans.version` is the optimistic-concurrency counter for later workflows.

## Current garment-intelligence core

The current cutover adds:

- multi-photo repeated roles and per-image declared/detected role/order;
- physical `garments` separated from `product_profiles`;
- `analysis_revisions`, evidence dossiers, immutable/superseding observations,
  proposed care plans, validation reports, and active revision/result pointers;
- garment identifiers, identity confirmations, and append-only service events;
- product identifiers and sourced lookup runs;
- conversation threads, messages, versioned summaries, revision references, and
  validation metadata;
- Phase 17 tenant-scoped exact evidence, canonical-plan, and rendered-answer cache
  records. pHash is stored only for candidate discovery, never automatic reuse.
- Phase 18 review/deletion lifecycle and Phase 19 low-cardinality model-run
  telemetry used for cost, latency, and failure monitoring.

The former one-extraction/one-result-per-scan constraints were removed by the
cutover migration. Retained data is transformed into revision-owned rows; no
old-schema read/write fallback remains.

All new tenant-owned rows require explicit `tenant_id`, UUID identifiers, UTC
timestamps, ownership indexes, and deletion/retention behavior. Stable identity
and care facts remain separate from timestamped stains, damage, wear, and other
condition observations. `analysed_before` comes from analysis history;
`cleaned_before` requires a confirmed performed/completed service event.

The 0004 downgrade deliberately raises rather than restoring the deleted legacy
schema. It is not a production rollback strategy after the destructive cutover.

The development seed creates `fabricassist-development` and
`admin@fabricassist.local`. Its authentication marker is intentionally not a
usable credential; Phase 6 will replace it with real credential handling.

For browser direct uploads, configure `FABRICASSIST_S3_PUBLIC_ENDPOINT_URL` to a browser-reachable MinIO/S3 URL; the API continues to use the internal `FABRICASSIST_S3_ENDPOINT_URL` for verification.

## Breaking cutover rollback

Migration `20260722_0004` is intentionally forward-only for retained data. It removes the legacy two-photo/extraction/result structures and does **not** recreate them on downgrade. Use a matching pre-cutover database backup plus the prior application release for an operational rollback; use forward fixes after the cutover is active.
