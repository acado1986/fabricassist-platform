# Current database baseline and planned garment-intelligence expansion

PostgreSQL is the FabricAssist system of record. Alembic currently has this
applied history:

- `20260721_0001` enables `citext` and `vector` and creates `tenants`, `users`,
  `refresh_sessions`, `scans`, `scan_images`, `idempotency_records`, and
  `ruleset_versions`.
- `20260721_0002` adds refresh rotation and direct-upload lifecycle fields.
- `20260721_0003` adds asynchronous analysis state plus `model_runs`,
  `label_extractions`, `care_results`, and `rendered_answers`.

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
`make migration-test` uses the isolated `fabricassist-postgres-test` Compose
service and `FABRICASSIST_POSTGRES_TEST_PORT` (default `5433`).

## Storage constraints

- Baseline primary keys and relationship keys use PostgreSQL UUID columns.
- Timestamp columns are timezone-aware and use PostgreSQL UTC-compatible
  `CURRENT_TIMESTAMP` values.
- Every tenant-owned baseline table has `tenant_id` plus a tenant index.
- `refresh_sessions` stores only `token_hash`, never a raw refresh token.
- `scan_images` stores private object metadata and checksums only; it does not
  store image bytes or presigned URLs.
- `scans.version` is the optimistic-concurrency counter for later workflows.

## Planned expansion

The approved architecture adds:

- multi-photo repeated roles and per-image declared/detected role/order;
- physical `garments` separated from `product_profiles`;
- `analysis_revisions`, evidence dossiers, immutable/superseding observations,
  proposed care plans, validation reports, and active revision/result pointers;
- garment identifiers, identity confirmations, and append-only service events;
- product identifiers and sourced lookup runs;
- conversation threads, messages, versioned summaries, revision references, and
  validation metadata.

The current unique constraints on one `label_extractions.scan_id` and one
`care_results.scan_id` are legacy v1 constraints. Replace them through a new
migration after revision-aware uniqueness/indexes exist. Retained data may be
transformed into revision-owned rows, after which the obsolete narrow result
shape and constraints are removed. No old-schema read/write fallback remains.

All new tenant-owned rows require explicit `tenant_id`, UUID identifiers, UTC
timestamps, ownership indexes, and deletion/retention behavior. Stable identity
and care facts remain separate from timestamped stains, damage, wear, and other
condition observations. `analysed_before` comes from analysis history;
`cleaned_before` requires a confirmed performed/completed service event.

The downgrade removes only this baseline and its extensions. It is intended for
empty and test databases, not a production rollback strategy after later schema
revisions exist.

The development seed creates `fabricassist-development` and
`admin@fabricassist.local`. Its authentication marker is intentionally not a
usable credential; Phase 6 will replace it with real credential handling.

For browser direct uploads, configure `FABRICASSIST_S3_PUBLIC_ENDPOINT_URL` to a browser-reachable MinIO/S3 URL; the API continues to use the internal `FABRICASSIST_S3_ENDPOINT_URL` for verification.

## Breaking cutover rollback

Migration `20260722_0004` is intentionally forward-only for retained data. It removes the legacy two-photo/extraction/result structures and does **not** recreate them on downgrade. Use a matching pre-cutover database backup plus the prior application release for an operational rollback; use forward fixes after the cutover is active.
