# FabricAssist production operations

This runbook is the active operational guide for the hosted FabricAssist
production deployment. It describes repository-level controls; provider
consoles remain authoritative for provider-specific status and billing.

## Guardrails

- Production uses the shared application and independently selected capability
  adapters. QStash, R2, Neon, Render, Pages, and Valkey are not domain or
  application implementations.
- PostgreSQL is authoritative for scans, evidence revisions, job intent,
  checkpoints, recovery, retention, and deletion state. QStash only delivers
  identifier-only messages and Valkey only accelerates or coordinates work.
- The API container runs one Uvicorn worker. It never starts Celery, runs
  Alembic, or performs seed work at startup.
- Keep runtime credentials in protected Render/GitHub settings. Never put
  secrets, image bytes, refresh tokens, complete presigned URLs, or provider
  payloads in logs, commits, or public Expo variables.
- Use synthetic smoke data only. A deterministic mock result may safely end in
  `completed`, `needs_review`, or another documented safe terminal state; it is
  not proof of an approved textile-care plan.

## Database and migrations

Use the Neon pooled TLS URL for API/worker runtime connections and the direct
TLS URL only for Alembic and administrative migrations:

```text
FABRICASSIST_DATABASE_URL=<pooled PostgreSQL URL>?sslmode=require
FABRICASSIST_DATABASE_MIGRATION_URL=<direct PostgreSQL URL>?sslmode=require
```

The protected release migration job applies the selected immutable revision
before API or web deployment. Do not run migrations at Render startup and do
not automatically downgrade PostgreSQL during rollback. Record the migration
head with the release SHA and smoke outcome. Never copy customer data into a
smoke or test database.

PostgreSQL connection pools, readiness retries, job recovery, and deletion
retry limits are typed settings. Tune them only after observing connection
usage and durable checkpoint behavior.

## Private R2 storage

Cloudflare R2 is selected through the existing S3-compatible object-storage
adapter. It must remain a private bucket with server-generated tenant-scoped
keys and application-only object permissions:

```text
FABRICASSIST_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
FABRICASSIST_S3_PUBLIC_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
FABRICASSIST_S3_REGION=auto
FABRICASSIST_S3_FORCE_PATH_STYLE=false
```

Configure the bucket with the exact deployed Pages origin(s), no wildcard and
no trailing slash:

```json
[
  {
    "AllowedOrigins": ["https://<pages-project>.pages.dev"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["content-type"],
    "ExposeHeaders": ["etag"],
    "MaxAgeSeconds": 600
  }
]
```

Add an exact HTTPS custom domain origin when used. Browser clients receive
only short-lived, single-object presigned operations; they never receive R2
credentials or bucket-list permissions. Keep lifecycle deletion for the
server-generated `private/` key prefix at least as long as the configured
application image-retention window. Lifecycle is a safety net, not a
replacement for PostgreSQL deletion records and object-outbox processing.

The default local contract is `make test-object-storage`. The opt-in R2
contract requires a disposable bucket/prefix and protected credentials:

```bash
FABRICASSIST_R2_SMOKE=1 make test-object-storage-r2
```

Do not run the live contract against customer data or the production bucket.

## QStash delivery

Production selects `FABRICASSIST_JOB_DISPATCHER=qstash`. Configure the token,
current signing key, next signing key, and an exact HTTPS destination ending at
`/internal/jobs/qstash`. The endpoint verifies raw request bytes, the issuer,
expiration, body digest, current/next key overlap, and the exact destination.

Messages contain only their schema version and identifiers. PostgreSQL records
publication intent and correlation IDs before external publication; checkpoint
claims make duplicate deliveries harmless. The API recovery loop republishes
committed but unpublished work and retries transient object deletions without a
scheduler-specific business implementation.

For signing-key rotation, configure the new key as `next` while retaining the
old `current`, verify signed delivery, then promote the key and configure a new
next key. Never rotate only one side of the overlap or print signing keys in an
incident record.

## Render API and Pages

The Render production service uses `backend/Dockerfile`, has automatic branch
deployment disabled, and exposes `/api/v1/health/live` as its health check.
The protected workflow sends the selected immutable SHA through the deploy hook,
waits for liveness/readiness, and verifies `X-FabricAssist-Revision` before
acceptance. Cloudflare Pages receives the shared Expo static export from that
same SHA. Only `EXPO_PUBLIC_FABRICASSIST_API_URL` and
`EXPO_PUBLIC_FABRICASSIST_ENVIRONMENT=production` may enter the web bundle.

Do not add a Render pre-deploy migration command. Do not put credentials in
Docker build arguments. A retention/cleanup pass may be run manually from the
**Run retention** GitHub Actions workflow
(`.github/workflows/run-retention.yml`). This avoids adding a separate Render
Cron service while keeping production credentials in protected GitHub settings.
The workflow uses the same scheduler-independent
`backend/scripts/run_retention.py` entry point.

Configure these repository Actions secrets: `FABRICASSIST_DATABASE_URL`,
`FABRICASSIST_S3_ENDPOINT_URL`, `FABRICASSIST_S3_ACCESS_KEY`,
`FABRICASSIST_S3_SECRET_KEY`, and `FABRICASSIST_S3_BUCKET`. Configure the
repository Actions variable `FABRICASSIST_MERGED_GARMENT_RETENTION_DAYS` (for
example, `30`). Run it from **GitHub → Actions → Run retention → Run workflow**.
FabricAssist loads only `FABRICASSIST_`-prefixed settings.

## Release smoke and resilience checks

Run the protected production smoke after deployment, recovery, and rollback.
It verifies liveness/readiness, synthetic login, draft creation, direct private
upload, upload completion, idempotent analysis replay, terminal safe status,
result reload, and deletion through the normal lifecycle. It must not print
credentials, image bytes, refresh tokens, or complete presigned URLs.

Before accepting a release, use synthetic data to verify:

| Scenario | Expected behavior |
| --- | --- |
| Blurred image | Better-image/review outcome without invented permission |
| Provider timeout | Bounded retry or failure without a permanently locked scan |
| Temporary database failure | Durable checkpoint remains recoverable |
| Continuation publication failure | Recovery republishes without duplicate results |
| R2 validation/deletion failure | Safe upload/deletion state and bounded retry |
| Invalid QStash signature | Request rejected without work creation |
| Invalid message schema | Explicit non-retry response |
| Local regression | Celery/PostgreSQL/MinIO/Valkey checks remain runnable |

Use `make release-live-smoke` only with protected values for an already deployed
production service. Hosted Neon, R2, QStash, Render, and Pages operations are
opt-in and are not part of default local CI.

## Quota and outage response

Monitor database connections, R2 storage/failed requests, QStash deliveries
and retries, Render health/cold starts, Pages deployment status, Valkey
availability, queue age, model calls, review rate, and object deletion backlog.
Configure provider budget alerts in provider dashboards; do not encode changing
vendor quotas in application code.

When a capacity or quota alarm fires, stop onboarding or pause new analysis
dispatch if required. Preserve PostgreSQL state and do not delete objects to
make room outside the normal lifecycle. Correct the provider/configuration
problem, then run readiness and the affected smoke/resilience check before
reopening traffic.

## Rollback and troubleshooting

Rollback is a selected known-good immutable tag or exact commit, never a tag
rewrite and never an automatic database downgrade. Confirm queued message
compatibility and the recorded migration head before redeploying. If the
selected revision fails quality or smoke, leave production in a safe
maintenance state and fix forward.

For incidents, record only a release SHA, timestamp, affected scan/job ID, and
redacted workflow reference. Inspect, in order: settings/profile and selected
adapters; pooled/direct database URLs and TLS; exact API/Pages/R2 CORS origins;
QStash destination, signature overlap, and durable checkpoint; object metadata
and deletion outbox; then liveness/readiness and smoke output. Never capture
secrets, signed request bodies, image data, or complete presigned URLs.

A leaked credential is compromised: revoke it at the owning provider, update
protected settings, redeploy the approved revision, and run the relevant smoke.
Document the incident without reproducing the value.
