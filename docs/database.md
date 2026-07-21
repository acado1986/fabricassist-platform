# Phase 5 database baseline

PostgreSQL is the FabricAssist system of record. Alembic manages the initial
baseline revision (`20260721_0001`); it enables `citext` and `vector` and creates
only `tenants`, `users`, `refresh_sessions`, `scans`, `scan_images`,
`idempotency_records`, and `ruleset_versions`.

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

The downgrade removes only this baseline and its extensions. It is intended for
empty and test databases, not a production rollback strategy after later schema
revisions exist.

The development seed creates `fabricassist-development` and
`admin@fabricassist.local`. Its authentication marker is intentionally not a
usable credential; Phase 6 will replace it with real credential handling.

For browser direct uploads, configure `FABRICASSIST_S3_PUBLIC_ENDPOINT_URL` to a browser-reachable MinIO/S3 URL; the API continues to use the internal `FABRICASSIST_S3_ENDPOINT_URL` for verification.
