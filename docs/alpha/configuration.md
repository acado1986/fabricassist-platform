# Alpha configuration

Phase 1 introduces typed configuration only. It does not publish to QStash,
change local Celery/Valkey/MinIO behavior, or deploy a hosted service.

## Safe template

Copy `.env.alpha.example` to an ignored file or configure its values in the
provider dashboard. It intentionally contains placeholders, not credentials.
Never expose database, R2, QStash, provider, JWT, or refresh-token secrets in
`EXPO_PUBLIC_*` variables.

## Required alpha settings

Set `FABRICASSIST_ENVIRONMENT=alpha`,
`FABRICASSIST_DEPLOYMENT_PROFILE=alpha`, and
`FABRICASSIST_JOB_DISPATCHER=qstash`. QStash selection requires a publish token,
current signing key, next signing key, and an HTTPS destination URL. Alpha also
requires explicit HTTPS CORS origins, a non-local PostgreSQL URL, an HTTPS
non-MinIO S3 endpoint, and at most three images per scan.

`FABRICASSIST_VALKEY_URL` is not required by alpha settings when QStash is
selected. The current API composition still uses Valkey for rate limiting; no
runtime composition change is made in this phase.

`FABRICASSIST_DATABASE_MIGRATION_URL` is required in alpha and is selected by
Alembic for direct administrative migration connections; see
[`neon-database.md`](neon-database.md). Render builds only the existing API
container and obtains these values from Render environment settings; see
[`render-api.md`](render-api.md). `FABRICASSIST_S3_REGION`,
`FABRICASSIST_VISION_MAX_CONCURRENCY`, `FABRICASSIST_JOB_STAGE_BUDGET_SECONDS`,
and `FABRICASSIST_DEFAULT_IMAGE_RETENTION_DAYS` are typed for the relevant
deployment profiles without changing local defaults.

## Local and production compatibility

Existing defaults remain `environment=development`,
`deployment_profile=local`, and `job_dispatcher=celery`. Production validation
is unchanged. Existing `make check` remains the local quality gate.

Run alpha configuration checks without contacting a provider:

```bash
make check-alpha-config
```
