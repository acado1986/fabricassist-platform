# Prerelease configuration

The prerelease profile is a configuration-selected deployment of the canonical
FabricAssist application. It does not fork the API, frontend, or domain model;
only composition-root capability adapters differ from local and production.

## Safe template

Copy `.env.alpha.example` to an ignored file or configure its values in the
provider dashboard. It intentionally contains placeholders, not credentials.
Never expose database, R2, QStash, provider, JWT, or refresh-token secrets in
`EXPO_PUBLIC_*` variables.

For the meaning of every variable and the difference between local Docker and
hosted prerelease, see the repository-wide [environment reference](../../environment.md).

## Required prerelease settings

Set `FABRICASSIST_ENVIRONMENT=alpha`,
`FABRICASSIST_DEPLOYMENT_PROFILE=alpha`, and
`FABRICASSIST_JOB_DISPATCHER=qstash`. QStash selection requires a publish token,
current signing key, next signing key, and an HTTPS destination URL. Prerelease also
requires explicit HTTPS CORS origins, a non-local PostgreSQL URL, an HTTPS
non-MinIO S3 endpoint, and at most three images per scan.

Prerelease explicitly selects its bounded optional adapters:

```text
FABRICASSIST_HOT_CACHE_BACKEND=noop
FABRICASSIST_RATE_LIMITER_BACKEND=noop
FABRICASSIST_CONCURRENCY_GATE_BACKEND=noop
FABRICASSIST_EVIDENCE_PROVIDER=mock
FABRICASSIST_CARE_PLANNER_PROVIDER=mock
FABRICASSIST_CHAT_PROVIDER=mock
FABRICASSIST_OBJECT_STORAGE_BACKEND=s3
FABRICASSIST_PRODUCT_INFORMATION_PROVIDER=mock
```

`FABRICASSIST_VALKEY_URL` is not required when every Valkey-backed capability is
disabled. `FABRICASSIST_CELERY_BROKER_URL` is unused when QStash is selected.
These no-op choices are for the documented hosted prerelease quotas; production
startup rejects no-op rate limiting and concurrency.

`FABRICASSIST_DATABASE_MIGRATION_URL` is required in the prerelease profile and is selected by
Alembic for direct administrative migration connections; see
[`neon-database.md`](neon-database.md). Render builds only the existing API
container and obtains these values from Render environment settings; see
[`render-api.md`](render-api.md). `FABRICASSIST_S3_REGION`,
`FABRICASSIST_VISION_MAX_CONCURRENCY`, `FABRICASSIST_JOB_STAGE_BUDGET_SECONDS`,
and `FABRICASSIST_DEFAULT_IMAGE_RETENTION_DAYS` are typed for the relevant
deployment profiles without changing local defaults.

The API process runs the PostgreSQL-authoritative recovery loop used by both
QStash and Celery deployments:

```text
FABRICASSIST_PUBLICATION_RECOVERY_INTERVAL_SECONDS=30
FABRICASSIST_PUBLICATION_RECOVERY_BATCH_SIZE=100
FABRICASSIST_DELETION_MAX_ATTEMPTS=5
```

It republishes committed analysis/conversation intents and retries transient
object deletions without requiring a paid scheduler or a repeated customer
request.

## Local and production compatibility

Existing defaults remain `environment=development`,
`deployment_profile=local`, `job_dispatcher=celery`, and Valkey capability
adapters. Existing `make check` remains the local quality gate.

Run prerelease configuration checks without contacting a provider:

```bash
make check-alpha-config
```
