# FabricAssist Free-Alpha Deployment Implementation Plan — Revised

**Status:** Ready for implementation  
**Purpose:** Add a $0-oriented alpha deployment profile without forking or weakening the existing production-ready architecture  
**Git branch:** `feat/free-alpha-deployment`  
**Git worktree:** `../fabricassist-alpha`  
**Target alpha stack:** Cloudflare Pages, Render, Neon, Cloudflare R2, Upstash QStash
**Local stack preserved:** Docker Compose, PostgreSQL, Valkey, MinIO, Celery  
**Production path preserved:** AWS ECS/Fargate, RDS, ElastiCache/Valkey, S3

---

## 1. Implementation decision

The free alpha is a **deployment profile in the existing FabricAssist codebase**.

It is not:

- A fork of the backend.
- A separate frontend.
- A permanent `alpha` branch.
- A replacement for Celery.
- A replacement for the production AWS architecture.
- A compatibility layer around obsolete domain behavior.

The alpha profile adds:

- A QStash implementation of the existing job-dispatch boundary.
- A signed internal HTTP delivery endpoint.
- Configuration for Neon and Cloudflare R2.
- A Render API deployment.
- A Cloudflare Pages static web deployment.
- Alpha-specific CI, smoke testing, release, and rollback procedures.

The deployment choice is made in the composition root through typed configuration.

```text
Same application and domain code
│
├── Local
│   ├── CeleryJobDispatcher
│   ├── Valkey
│   ├── PostgreSQL container
│   └── MinIO
│
├── Free alpha
│   ├── QStashJobDispatcher
│   ├── Neon PostgreSQL
│   ├── Cloudflare R2
│   ├── Render API
│   └── Cloudflare Pages
│
└── Production
    ├── CeleryJobDispatcher
    ├── managed broker
    ├── RDS PostgreSQL
    ├── S3
    └── ECS API and worker
```

---

## 2. Non-negotiable architecture rules

1. PostgreSQL remains authoritative for scan state, checkpoints, completed results, idempotency, and retries.
2. QStash is a transport mechanism, not the source of business state.
3. Celery remains supported and remains the default for local development unless existing repository configuration says otherwise.
4. The existing S3-compatible object-storage adapter must support MinIO, R2, and AWS S3 through configuration.
5. No image bytes, presigned URLs, credentials, complete dossiers, or customer tokens may be included in QStash messages.
6. Internal job execution must be idempotent under duplicate and concurrent delivery.
7. A customer-facing AI result must still pass the existing deterministic validation gates.
8. Alpha-specific behavior must be selected at the composition root, not through scattered `if environment == "alpha"` conditions.
9. API and frontend production defaults must not change.
10. External provider secrets must never be committed, included in Expo public variables, or pasted into Codex prompts.

---

## 3. Git branch and worktree setup

### 3.1 Prepare the main checkout

```bash
cd /path/to/fabricassist-platform

git status
git switch main
git pull --ff-only

make check
```

Do not create the worktree until the main checkout is clean.

### 3.2 Create the branch and worktree

```bash
git worktree add \
  -b feat/free-alpha-deployment \
  ../fabricassist-alpha \
  main
```

Verify:

```bash
git worktree list

cd ../fabricassist-alpha
git branch --show-current
git status
git rev-parse HEAD
```

Expected branch:

```text
feat/free-alpha-deployment
```

Record the baseline SHA in the implementation notes.

### 3.3 Worktree environment isolation

Create:

```text
.env.alpha.example      # committed
.env.alpha.local        # ignored
```

Initialize the local file:

```bash
cp .env.alpha.example .env.alpha.local
```

Recommended ignore rules:

```gitignore
.env
.env.*
!.env.example
!.env.alpha.example
```

When two Compose stacks are running locally:

```env
COMPOSE_PROJECT_NAME=fabricassist-alpha

FABRICASSIST_API_HOST_PORT=8100
FABRICASSIST_POSTGRES_HOST_PORT=5433
FABRICASSIST_VALKEY_HOST_PORT=6380
FABRICASSIST_MINIO_HOST_PORT=9100
FABRICASSIST_MINIO_CONSOLE_HOST_PORT=9101
```

Do not copy production credentials into this worktree.

---

## 4. Delivery phases

| Phase | Objective | Suggested commit |
|---:|---|---|
| 0 | Inventory the existing implementation | No implementation commit |
| 1 | Add typed alpha configuration | `feat(config): add free alpha deployment profile` |
| 2 | Add the QStash dispatcher | `feat(jobs): add QStash dispatcher` |
| 3 | Add signed, checkpointed HTTP job execution | `feat(jobs): add checkpointed HTTP job execution` |
| 4 | Validate the existing S3 adapter against R2 | `feat(storage): support Cloudflare R2 deployment` |
| 5 | Add the Neon database profile | `feat(database): add Neon alpha configuration` |
| 6 | Add the Render API deployment | `feat(deployment): add Render alpha API deployment` |
| 7 | Add the Cloudflare Pages web deployment | `feat(deployment): add Cloudflare Pages alpha web deployment` |
| 8 | Add CI, release, smoke, and rollback workflows | `ci(alpha): add verified deployment workflows` |
| 9 | Complete runbooks and acceptance testing | `docs(alpha): complete deployment and rollback runbooks` |

Implement only one phase at a time. Every phase must finish with a clean, reviewed diff and passing targeted checks.

---

# Phase 0 — Existing implementation inventory

## Objective

Map the actual code before changing it. Do not assume that file paths in this plan exactly match the repository.

## Inspect

- Current `JobDispatcher` port or equivalent.
- All direct Celery calls from application services.
- Celery task payloads and retry policy.
- Persisted scan stages and checkpoints.
- Existing idempotency records.
- Existing PostgreSQL locking or leasing behavior.
- S3 adapter construction and addressing style.
- FastAPI composition root.
- Current settings classes.
- Current OpenAPI generation.
- Existing internal routes.
- Backend Dockerfile build context.
- Expo web output configuration.
- Existing GitHub Actions versions and conventions.
- Existing migration command.
- Existing `AGENTS.md` instructions.

## Required output

Create:

```text
docs/alpha/implementation-inventory.md
```

It must contain:

- Actual relevant file paths.
- Existing interfaces that can be reused.
- Gaps requiring new code.
- Existing test commands.
- Any discrepancy between this plan and the repository.
- Recommended exact implementation order.

## Stop condition

No production code changes. Stop after the inventory is reviewed.

---

# Phase 1 — Typed alpha configuration

## Objective

Add an explicit alpha deployment profile without changing local or production behavior.

## Configuration types

Adapt naming to the repository’s current conventions.

```python
class DeploymentProfile(str, Enum):
    LOCAL = "local"
    ALPHA = "alpha"
    PRODUCTION = "production"


class JobDispatcherType(str, Enum):
    CELERY = "celery"
    QSTASH = "qstash"
```

## Environment variables

```env
FABRICASSIST_ENVIRONMENT=alpha
FABRICASSIST_DEPLOYMENT_PROFILE=alpha
FABRICASSIST_JOB_DISPATCHER=qstash

FABRICASSIST_DATABASE_URL=
FABRICASSIST_DATABASE_MIGRATION_URL=

FABRICASSIST_S3_ENDPOINT_URL=
FABRICASSIST_S3_REGION=auto
FABRICASSIST_S3_BUCKET=fabricassist-alpha
FABRICASSIST_S3_FORCE_PATH_STYLE=false

FABRICASSIST_QSTASH_TOKEN=
FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY=
FABRICASSIST_QSTASH_NEXT_SIGNING_KEY=
FABRICASSIST_QSTASH_DESTINATION_URL=

FABRICASSIST_MAX_IMAGES_PER_SCAN=3
FABRICASSIST_VISION_MAX_CONCURRENCY=1
FABRICASSIST_JOB_STAGE_BUDGET_SECONDS=75
FABRICASSIST_DEFAULT_IMAGE_RETENTION_DAYS=7
```

Use the existing setting names where equivalent settings already exist. Do not introduce duplicate variables.

## Validation

When the effective dispatcher is `qstash`:

- QStash publish credentials are required.
- Current and next signing keys are required for delivery verification.
- Destination URL must be HTTPS.
- Valkey and Celery result-backend settings must not be required.
- Wildcard production-like CORS must be rejected.
- Local PostgreSQL and MinIO defaults must be rejected in the hosted alpha profile.
- Vision concurrency defaults to one.
- The initial alpha limit defaults to three completed images per scan.
- No secret setting is exposed through `EXPO_PUBLIC_*`.

## Files

Expected locations, adjusted after Phase 0:

```text
backend/src/fabricassist/settings.py
backend/tests/unit/test_settings.py
.env.alpha.example
docs/alpha/configuration.md
```

## Tests

- Existing local settings continue to load unchanged.
- Existing production settings continue to load unchanged.
- Alpha settings succeed with all required values.
- Alpha settings fail with missing QStash signing keys.
- Alpha settings do not require Valkey.
- Wildcard CORS is rejected.
- Secret-looking variables are absent from frontend public configuration.

## Acceptance

```bash
make check
make check-alpha-config
git diff --check
```

---

# Phase 2 — QStash job-dispatch adapter

## Objective

Add QStash as another implementation of the existing job-dispatch port.

Do not replace or modify the public behavior of the Celery adapter.

## Target design

```text
Application service
      │
      ▼
JobDispatcher port
      │
      ├── CeleryJobDispatcher
      └── QStashJobDispatcher
```

Suggested infrastructure structure:

```text
backend/src/fabricassist/infrastructure/jobs/
├── celery.py
├── qstash.py
└── factory.py
```

Use the actual existing paths discovered in Phase 0.

## Message schema

Define and version a strict message model:

```json
{
  "message_schema_version": 1,
  "scan_id": "uuid",
  "operation_key": "analyse:uuid",
  "stage": "validate_uploaded_images",
  "revision_id": "uuid"
}
```

Only identifiers and versioned routing metadata are allowed.

Do not include:

- Image bytes.
- Object-storage credentials.
- Presigned URLs.
- Full evidence dossiers.
- JWTs or refresh tokens.
- Provider API keys.
- User-supplied unrestricted URLs.

## Dispatcher behavior

- Publish to the configured HTTPS destination.
- Use a stable deduplication identifier derived from the operation key and stage.
- Use bounded HTTP timeout.
- Categorize publish errors as transient, permanent authentication/configuration, or invalid payload.
- Redact the QStash token and message-sensitive metadata from logs.
- Keep PostgreSQL idempotency authoritative.
- Preserve the existing Celery adapter as the local/default implementation.

## Composition root

```python
def create_job_dispatcher(settings: Settings) -> JobDispatcher:
    match settings.job_dispatcher:
        case JobDispatcherType.CELERY:
            return CeleryJobDispatcher(...)
        case JobDispatcherType.QSTASH:
            return QStashJobDispatcher(...)
        case _:
            raise UnsupportedJobDispatcherError(
                settings.job_dispatcher
            )
```

Adapt this to the existing dependency-injection style.

## Tests

- Correct endpoint and headers.
- Correct versioned JSON payload.
- Stable deduplication ID.
- Duplicate publication request produces the same transport key.
- Token never appears in logs or raised messages.
- Timeout maps to a retryable dispatch failure.
- Authentication/configuration failure maps to a permanent failure.
- Invalid local message fails before network I/O.
- Existing Celery tests continue passing.

## Acceptance

```bash
make test-qstash
make check
git diff --check
```

---

# Phase 3 — Signed, checkpointed HTTP job execution

## Objective

Allow QStash to push one bounded, idempotent analysis stage to the API.

Do not run the entire analysis as one long web request.

## Internal endpoint

Recommended shape:

```http
POST /api/v1/internal/jobs/scans/{scan_id}/execute-stage
```

The exact path may follow existing API conventions.

## Delivery verification

The handler must:

1. Read and preserve the raw request body.
2. Verify the QStash signature against current and next signing keys.
3. Verify expiration and destination URL claims.
4. Verify the request-body hash.
5. Parse the strict message schema only after signature verification.
6. Reject unsupported message schema versions.

Do not use normal customer JWT authentication for this route.

## Execution flow

Each delivery performs one bounded stage:

```text
validate_uploaded_images
    ↓
normalize_images
    ↓
calculate_fingerprints
    ↓
resolve_garment_identity
    ↓
resolve_exact_evidence_cache
    ↓
extract_new_evidence
    ↓
decode_and_lookup_products
    ↓
merge_evidence_revision
    ↓
propose_care_plan
    ↓
validate_care_plan
    ↓
resolve_validated_result_cache
    ↓
render_answers
    ↓
finalize_revision_and_scan
```

Use the actual stage model already present in the application. Do not invent duplicate orchestration if persisted checkpoints already exist.

## Per-delivery transaction

Each invocation must:

1. Load the operation from PostgreSQL.
2. Acquire a short database advisory lock, row lease, or existing equivalent.
3. Check scan, revision, operation, and stage state.
4. Return success if the stage is already complete.
5. Execute one stage within the configured budget.
6. Persist checkpoint and result state.
7. Commit the transaction.
8. Publish the next stage.
9. Recover safely if publication fails after checkpoint commit.

The design must cover the “checkpoint committed, next message not published” gap through an outbox, redispatch record, or safe reconciliation mechanism. Do not rely on a single in-memory sequence.

## Time budget

```env
FABRICASSIST_JOB_STAGE_BUDGET_SECONDS=75
```

This is an application budget, not a promise about a hosting provider’s exact timeout.

A stage approaching the budget must:

- Persist a continuation cursor or safe checkpoint.
- Publish a continuation message.
- Return before the hosting connection is terminated.

## Response policy

QStash retries non-2xx responses by default. Use this policy:

| Situation | HTTP response |
|---|---:|
| Stage completed | `204` |
| Stage already completed | `204` |
| Deterministically blocked | `204` after state persistence |
| Needs better image | `204` after state persistence |
| Deleted or obsolete operation | `204` as an idempotent no-op |
| Temporary database/provider/storage failure | `503` |
| Valid signed request with permanently invalid payload | `489` plus `Upstash-NonRetryable-Error: true` |
| Invalid or missing signature | `401` |
| Unexpected internal error | `500` |

Do not assume that ordinary `400`, `401`, or `404` responses are automatically non-retryable.

## Security

- Exclude the route from the customer-generated API client where practical.
- Never expose QStash signing details in responses.
- Rate-limit invalid signatures separately if supported.
- Do not log raw bodies if they contain identifiers considered sensitive.
- Require an exact configured destination URL.
- Add an optional defense-in-depth internal header only if it can be safely managed and rotated.
- Prevent user input from selecting arbitrary stages.

## Failure tests

- Valid signature.
- Current signing key.
- Next signing key.
- Modified body after signing.
- Incorrect destination URL.
- Expired signature.
- Unsupported schema version.
- Duplicate delivery.
- Concurrent delivery.
- Crash before checkpoint.
- Crash after checkpoint.
- Failure publishing the next stage.
- Reconciliation of a committed-but-undispatched stage.
- Temporary provider failure and retry.
- Permanent invalid payload and non-retry response.
- Deleted operation no-op.
- Final state after repeated delivery.
- Customer access to internal route denied.

## Acceptance

```bash
make test-qstash
make test-worker
make check
git diff --check
```

---

# Phase 4 — Cloudflare R2 storage profile

## Objective

Use the existing S3-compatible adapter against R2 without creating a domain-specific R2 adapter.

## Configuration

```env
FABRICASSIST_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
FABRICASSIST_S3_REGION=auto
FABRICASSIST_S3_BUCKET=fabricassist-alpha
FABRICASSIST_S3_FORCE_PATH_STYLE=false
```

## Required changes

- Support `region_name="auto"` where required by the configured endpoint.
- Allow virtual-host-compatible behavior for R2.
- Keep path-style support for MinIO.
- Keep the bucket private.
- Continue using server-generated object keys.
- Continue verifying object metadata after direct upload.
- Add alpha lifecycle/retention documentation.
- Ensure presigned browser uploads use the R2 S3 endpoint.
- Add the exact Cloudflare Pages origin to R2 CORS.
- Keep previews short-lived and private.

## Adapter rule

Prefer:

```text
Boto3ObjectStorageAdapter
    endpoint = MinIO | Cloudflare R2 | AWS S3
```

Do not create `CloudflareR2StorageAdapter` unless a proven incompatibility cannot be represented by existing adapter configuration.

## Tests

Default CI:

- Run the full storage contract against MinIO.

Protected/manual smoke:

- Run the same contract against a dedicated R2 test prefix.

Cover:

- Presigned upload.
- Metadata verification.
- Private object read.
- Derivative write.
- Preview.
- Delete.
- Invalid key.
- Expired URL.
- CORS.
- No public listing.
- Tenant prefix isolation.

## Acceptance

```bash
make test-object-storage
make check
git diff --check
```

---

# Phase 5 — Neon PostgreSQL profile

## Objective

Run the existing SQLAlchemy and Alembic implementation against Neon without changing repository or domain behavior.

## URLs

Use separate runtime and migration settings:

```env
# Runtime application connection, normally pooled
FABRICASSIST_DATABASE_URL=postgresql+psycopg://...-pooler.../fabricassist?sslmode=require

# Migration and administrative connection, normally direct
FABRICASSIST_DATABASE_MIGRATION_URL=postgresql+psycopg://.../fabricassist?sslmode=require
```

## Required changes

- Require TLS for the hosted alpha database.
- Keep one SQLAlchemy session per use case/task.
- Configure a small pool appropriate to the free API instance.
- Use `pool_pre_ping`.
- Add bounded connection retry for cold start/transient connection errors.
- Run migrations through the direct migration URL.
- Confirm required extensions, including `citext` and `vector`.
- Seed a dedicated alpha tenant and administrator.
- Do not copy production users, scans, garments, conversations, or images.

Suggested starting pool settings, subject to measurement:

```python
pool_size = 2
max_overflow = 1
pool_pre_ping = True
pool_recycle = 300
```

Do not duplicate engine factories solely for Neon. Configure the existing one.

## Tests

- Empty database to migration head.
- Previous supported migration to head.
- Seed idempotency.
- Runtime pooled connection.
- Direct migration connection.
- TLS-required validation.
- Cold connection recovery.
- Transaction rollback.
- Extension availability.
- Readiness behavior while database is waking.

## Acceptance

```bash
make test-migrations
make check
git diff --check
```

---

# Phase 6 — Render API deployment

## Objective

Deploy one FastAPI web service using the existing backend Dockerfile and the
operator-configured Render Docker web-service tier.

## Dockerfile inspection

Phase 0 must determine the correct build context.

The implementation inventory confirms that `backend/` is the Docker build root:

```text
Root Directory: backend
Dockerfile Path: Dockerfile
```

## Runtime

Recommended effective command:

```bash
uvicorn fabricassist.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers 1
```

Reuse the Dockerfile’s existing command when it already handles `${PORT}` correctly.

## Required Render deployment settings

```yaml
Root Directory: backend
Dockerfile Path: Dockerfile
Health Check Path: /api/v1/health/live
Region: Frankfurt
Auto-Deploy: Off
```

Use a protected `RENDER_DEPLOY_HOOK_URL` in GitHub Actions. The workflow passes
the quality job's resolved SHA as the deploy hook `ref` and waits for liveness
and readiness. Do not use a generic latest-branch deployment trigger.

## Environment strategy

Create Render runtime values once in the Render dashboard.

Set them as service environment variables:

```yaml
FABRICASSIST_ENVIRONMENT=alpha
FABRICASSIST_DEPLOYMENT_PROFILE=alpha
FABRICASSIST_JOB_DISPATCHER=qstash
FABRICASSIST_DATABASE_URL=<pooled Neon TLS URL>
FABRICASSIST_DATABASE_MIGRATION_URL=<direct Neon TLS URL>
FABRICASSIST_S3_ENDPOINT_URL=<private R2 endpoint>
FABRICASSIST_S3_ACCESS_KEY=<R2 access key>
FABRICASSIST_S3_SECRET_KEY=<R2 secret key>
FABRICASSIST_QSTASH_TOKEN=<QStash publish token>
FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY=<current signing key>
FABRICASSIST_QSTASH_NEXT_SIGNING_KEY=<next signing key>
```

Add all other existing required secure settings, including JWT and AI-provider credentials.

Do not recreate unchanged Render values on every deploy.

## Startup rules

The hosted API must not:

- Automatically run Alembic.
- Automatically seed users.
- Start Celery.
- Require Valkey when QStash is selected.
- Depend on the ephemeral filesystem.
- Start multiple application workers.
- Load test fixtures at startup.

## Smoke tests

- Liveness.
- Readiness.
- Render cold start.
- Neon reconnection.
- R2 access.
- QStash signature verification.
- One-image scan.
- Three-image scan.
- Bounded memory during normalization.
- No credentials in logs.

## Acceptance

The service is healthy and an end-to-end mock-provider scan completes.

---

# Phase 7 — Cloudflare Pages web deployment

## Objective

Deploy the Expo web static export with only public runtime/build configuration.

## Expo configuration

```json
{
  "expo": {
    "web": {
      "output": "static"
    }
  }
}
```

## Build

```bash
pnpm --dir frontend install --frozen-lockfile

pnpm --dir frontend \
  --filter fabricassist-app \
  exec expo export --platform web
```

Expected output:

```text
frontend/apps/client/dist/
```

Confirm the actual package name and output path during Phase 0.

## Public variables

```env
EXPO_PUBLIC_FABRICASSIST_API_URL=https://<alpha-api>.onrender.com
EXPO_PUBLIC_FABRICASSIST_ENVIRONMENT=alpha
```

Never expose:

- Database URLs.
- R2 access credentials.
- QStash credentials or signing keys.
- AI provider keys.
- JWT signing keys.
- Refresh-token hash keys.

## Cloudflare deployment action

Use the maintained Wrangler action:

```yaml
- name: Deploy frontend to Cloudflare Pages
  id: deploy-pages
  uses: cloudflare/wrangler-action@v3
  with:
    apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    command: >-
      pages deploy frontend/apps/client/dist
      --project-name=fabricassist-alpha
      --branch=main
    gitHubToken: ${{ secrets.GITHUB_TOKEN }}
```

Do not use the deprecated `cloudflare/pages-action`.

## API and R2 CORS

Allow the exact alpha origins:

```env
FABRICASSIST_CORS_ALLOWED_ORIGINS=https://fabricassist-alpha.pages.dev
```

Also add the deployed custom domain when introduced.

If preview branch deployments are enabled, define an explicit policy rather than allowing arbitrary wildcard origins.

## Tests

- Static export.
- Nested-route browser refresh.
- No secret patterns in generated JavaScript.
- API authentication.
- Direct R2 upload.
- Spanish and English catalogs.
- Mobile configuration remains independent.
- Exact CORS origin.
- Pages deployment URL captured from the action output.

## Acceptance

The web application loads from Pages and completes an authenticated mock-provider scan through the hosted API.

---

# Phase 8 — CI, deployment, smoke, and rollback

## Objective

Separate inexpensive deterministic CI from credential-consuming deployment and live smoke tests.

## Workflow set

```text
.github/workflows/
├── release-quality.yml
├── deploy-prerelease.yml
└── prerelease-live-smoke.yml
```

Reuse existing repository quality workflows when possible instead of duplicating them.

## 8.1 Routine alpha quality workflow

Trigger:

```yaml
on:
  pull_request:
  push:
    branches:
      - feat/free-alpha-deployment
      - main
```

It must not use Neon, R2, QStash, Render, Cloudflare, or AI-provider credentials.

Run:

- Backend lint, formatting, type checks, and unit tests.
- Existing Celery tests.
- QStash adapter tests with a synthetic HTTP transport.
- Signature tests with locally generated test keys.
- PostgreSQL-container integration tests.
- MinIO storage contract tests.
- OpenAPI/client drift.
- Expo static export.
- Secret scanning.

Recommended Make targets:

```bash
make check
make check-alpha-config
make test-qstash
make build-release-web
```

## 8.2 Alpha deployment workflow

Triggers:

```yaml
on:
  push:
    tags:
      - "v*-alpha*"
  workflow_dispatch:
    inputs:
      ref:
        description: Commit, branch, or tag to deploy
        required: true
```

Use the chosen ref consistently for checkout and deployment.

Jobs:

```text
quality
   ↓
migrate
   ↓
deploy-api ──┐
             ├──► live-smoke
deploy-web ──┘
```

### Rules

- Run deterministic quality checks first.
- Run Alembic with the explicit backend project and configuration paths.
- Migrations must be backward-compatible with the currently running API.
- Deploy the API with `service-instance-type: free`.
- Deploy the static frontend with `cloudflare/wrangler-action@v3`.
- Verify liveness and readiness after deployment.
- Run the live end-to-end smoke test **after** both deployments.
- Mark the deployment failed if the smoke test fails.

### Migration command

Use the repository’s existing migration target when available.

Otherwise:

```bash
uv run --project backend \
  alembic \
  -c backend/alembic.ini \
  upgrade head
```

## 8.3 Manual live-smoke workflow

Trigger:

```yaml
on:
  workflow_dispatch:
    inputs:
      base_url:
        description: Alpha API URL
        required: false
```

Purpose:

- Diagnose an already deployed environment.
- Re-run smoke tests after provider configuration changes.
- Validate recovery after an outage.
- Test before and after rollback.

It must not be described as proof for a candidate that has not yet been deployed.

## Live smoke coverage

- API liveness/readiness.
- Sign-in.
- Draft scan creation.
- Direct R2 upload.
- Analysis dispatch.
- QStash delivery.
- Neon checkpoint persistence.
- Mock-provider validated result.
- Duplicate idempotency key.
- Duplicate QStash delivery.
- Result reload.
- Deletion and R2 object removal.
- No secrets or presigned URLs in logs.

Use the mock provider for release smoke by default. Run a real Gemini smoke separately and sparingly.

## Rollback

Do not move or re-push a published release tag.

Preferred options:

### Manual redeploy of a known ref

Run `deploy-prerelease.yml` through `workflow_dispatch` with a previous good tag or commit.

### New rollback tag

```bash
git tag -a v0.1.0-alpha.2-rollback <previous-good-commit> \
  -m "Rollback alpha to previous good release"

git push origin v0.1.0-alpha.2-rollback
```

Rollback rules:

- Redeploy matching backend and frontend artifacts.
- Do not automatically downgrade PostgreSQL.
- Pause or disable new dispatch only when message/schema incompatibility requires it.
- Keep QStash message schemas versioned.
- Old queued messages must safely execute, no-op, or fail into a reviewed state.
- Verify liveness, readiness, and live smoke after rollback.

## Action pinning

Before merging:

- Use the action versions already approved by the repository where possible.
- Verify third-party action inputs against their current official README.
- Prefer commit-SHA pinning for production-sensitive workflows if that is the repository policy.
- Do not silently upgrade unrelated actions as part of this feature.

---

# Phase 9 — Runbooks and final acceptance

## Files

```text
docs/
└── alpha/
    ├── README.md
    ├── implementation-inventory.md
    ├── architecture.md
    ├── configuration.md
    ├── deployment.md
    ├── secrets.md
    ├── smoke-tests.md
    ├── rollback.md
    ├── quotas-and-limits.md
    └── troubleshooting.md

infrastructure/
└── alpha/
    ├── render/
    ├── cloudflare-pages/
    ├── cloudflare-r2/
    ├── neon/
    └── upstash-qstash/
```

Do not duplicate provider documentation. Record only FabricAssist-specific setup, required values, verification, and failure recovery.

## Deployment order

1. Create Neon alpha database.
2. Obtain runtime pooled URL and direct migration URL.
3. Apply migrations and seed the alpha tenant.
4. Create private R2 bucket, API credentials, CORS, and retention rules.
5. Create QStash credentials and record current/next signing keys.
6. Create Render runtime variables and protected deploy hook.
7. Deploy Render API.
8. Configure the final QStash destination URL.
9. Send and verify a signed synthetic delivery.
10. Create Cloudflare Pages project.
11. Build and deploy Expo web.
12. Add exact Pages origin to API and R2 CORS.
13. Run post-deployment live smoke.
14. Tag the accepted release.
15. Record deployment SHA, tag, migration head, and smoke result.

## End-to-end acceptance test

The alpha profile is accepted when:

1. A user opens FabricAssist from Cloudflare Pages.
2. The user registers or signs in.
3. The user creates a draft scan.
4. The user adds a garment image.
5. The user adds a care-label image.
6. Both upload directly to private R2 storage.
7. Upload completion is verified by the API.
8. Analysis is started with an idempotency key.
9. QStash receives a versioned identifier-only message.
10. The signed internal endpoint executes bounded stages.
11. Each checkpoint is durable in Neon.
12. The frontend polls and receives a validated result.
13. Refreshing the browser reopens the result.
14. Repeating the same idempotency key does not duplicate the result.
15. Duplicate QStash delivery does not duplicate work.
16. Deleting the scan removes private objects through the existing deletion lifecycle.
17. Logs contain no credentials, image bytes, full presigned URLs, or refresh tokens.

Also verify:

- Blurred image.
- Provider timeout.
- Temporary database failure.
- Next-stage publication failure.
- Render cold start.
- Neon cold start.
- R2 failure.
- Invalid QStash signature.
- Permanently invalid signed message.
- Three simultaneous alpha users.
- Three images in one scan.
- Existing local Celery flow still works.

---

## 5. Definition of done

- [ ] Phase 0 documents the real implementation before code changes.
- [ ] The work was completed on `feat/free-alpha-deployment` in `../fabricassist-alpha`.
- [ ] Alpha is configuration-driven and merged into `main`.
- [ ] No permanent alpha branch is retained.
- [ ] Celery remains supported and tested.
- [ ] QStash implements the existing job-dispatch boundary.
- [ ] QStash payloads are identifier-only and schema-versioned.
- [ ] QStash signatures are checked against raw request bytes and exact destination.
- [ ] Known permanent signed failures use QStash’s explicit non-retry response.
- [ ] Duplicate and concurrent delivery are safe.
- [ ] The committed-checkpoint/failed-next-publish gap is reconciled.
- [ ] PostgreSQL remains authoritative.
- [ ] The existing S3 adapter supports MinIO, R2, and AWS S3.
- [ ] Neon migrations pass from empty and previous supported schema.
- [ ] Render uses the backend Docker build root, one Uvicorn worker, disabled auto-deploy, and an exact-SHA deploy hook.
- [ ] Cloudflare uses `cloudflare/wrangler-action@v3`.
- [ ] The Expo web bundle contains no secrets.
- [ ] Routine CI consumes no external alpha quotas.
- [ ] Deployment smoke runs after API and frontend deployment.
- [ ] Rollback deploys a selected old ref without moving published tags.
- [ ] The local Celery/Valkey/MinIO flow still passes.
- [ ] The hosted Pages → Render → R2 → QStash → Neon flow passes.
- [ ] The accepted release is tagged, for example `v0.1.0-alpha.1`.
- [ ] The feature branch and worktree are removed after merge.
- [ ] Deployment and rollback runbooks were executed at least once.

---

# 6. Implementing this plan with Codex CLI

## 6.1 Install or update Codex CLI

On Linux or macOS:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Open the alpha worktree and start Codex:

```bash
cd ../fabricassist-alpha
codex
```

Sign in with the ChatGPT account when prompted.

## 6.2 Confirm project instructions

FabricAssist already has `AGENTS.md`. Do not regenerate or overwrite it blindly.

In Codex:

```text
/status
```

Then ask:

```text
List the AGENTS.md and other project instruction files you loaded. Summarize the rules that apply to this repository. Do not modify files.
```

Use `/init` only when the repository genuinely lacks an `AGENTS.md`.

## 6.3 Permissions

For implementation sessions, use the normal workspace-write sandbox and approval-on-request behavior:

```bash
codex \
  --sandbox workspace-write \
  --ask-for-approval on-request
```

Inside Codex, inspect or change permissions with:

```text
/permissions
```

Do not use unrestricted filesystem access for this implementation.

Keep network access disabled for ordinary code phases. Approve narrowly when a command truly needs to install a locked dependency or query an allowed provider endpoint.

Never give Codex:

- Production credentials.
- Neon passwords.
- R2 access keys.
- QStash tokens or signing keys.
- Render deploy-hook URLs or API tokens.
- Cloudflare API tokens.
- Gemini/OpenAI API keys.

Use placeholders and synthetic local tests. Configure real secrets manually in provider dashboards or GitHub Secrets.

## 6.4 Codex workflow rule

Use **one fresh Codex session per phase**.

Do not ask Codex to implement all nine phases in one turn.

For each phase:

1. Start with a clean Git status.
2. Ask Codex to read the plan and inspect existing code.
3. Require a short implementation proposal before edits.
4. Let it implement only the selected phase.
5. Require targeted tests.
6. Use `/review`.
7. Inspect `git diff`.
8. Commit manually after review.
9. Start a fresh session for the next phase.

This reduces context drift and makes each change independently reversible.

## 6.5 General phase prompt

Save the plan inside the repository as:

```text
docs/alpha/FREE_ALPHA_IMPLEMENTATION_PLAN.md
```

Use this prompt for each phase:

```text
Read these files first:

- AGENTS.md
- docs/architecture.md
- docs/IMPLEMENTATION_PLAN.md
- docs/alpha/FREE_ALPHA_IMPLEMENTATION_PLAN.md
- any nested AGENTS.md or AGENTS.override.md files that apply

We are working in the existing Git worktree on branch
feat/free-alpha-deployment. Do not create or switch branches and do not create
another worktree.

Implement only Phase <NUMBER>: <NAME> from the free-alpha implementation plan.

Before editing:
1. Inspect the existing implementation and relevant tests.
2. Report the actual files and interfaces you will reuse.
3. Identify any discrepancy between the plan and the repository.
4. Propose a focused checkpoint plan.

Implementation constraints:
- Preserve the current local Celery/Valkey/MinIO behavior.
- Preserve the future production AWS path.
- Do not introduce a parallel backend or frontend.
- Do not add scattered environment checks to domain/application modules.
- Keep PostgreSQL authoritative.
- Do not add secrets or real provider credentials.
- Do not begin a later phase.
- Do not commit changes.

Validation:
- Run the smallest targeted tests after each checkpoint.
- Run the phase acceptance commands from the plan.
- Fix failures caused by this phase before stopping.
- Do not claim commands passed unless you actually ran them.

At the end, report:
- Files changed.
- Design decisions.
- Commands run and results.
- Remaining risks.
- Any manual provider setup still required.
- Whether the phase acceptance criteria are satisfied.

Stop after this phase.
```

## 6.6 Phase 0 Codex prompt

```text
Read AGENTS.md, docs/architecture.md, docs/IMPLEMENTATION_PLAN.md, and
docs/alpha/FREE_ALPHA_IMPLEMENTATION_PLAN.md.

Perform only Phase 0, the existing implementation inventory.

Do not modify production code, dependencies, migrations, workflows, or
configuration. Inspect the repository and create only
docs/alpha/implementation-inventory.md.

The inventory must identify:
- the real JobDispatcher boundary;
- every direct Celery dependency;
- persisted scan stages/checkpoints;
- idempotency and locking;
- object-storage construction;
- settings and composition root;
- backend Docker build context;
- Expo web build configuration;
- migration commands;
- current GitHub Actions conventions;
- exact tests relevant to Phases 1–8;
- discrepancies between the plan and actual repository.

Run only read-only or documentation validation commands. Stop when the inventory
is complete. Do not commit.
```

Review the inventory yourself before continuing.

## 6.7 Phase 1 Codex prompt

```text
Implement only Phase 1, typed alpha configuration.

Use the actual settings and dependency-injection patterns documented in
docs/alpha/implementation-inventory.md.

Do not implement QStash HTTP calls or internal endpoints yet.
Do not change local or production defaults.
Add strict tests for alpha validation and create .env.alpha.example without
real secrets.

Run targeted settings tests, make check-alpha-config if created, make check, and
git diff --check. Stop after Phase 1. Do not commit.
```

## 6.8 Phase 2 Codex prompt

```text
Implement only Phase 2, the QStash JobDispatcher adapter.

Reuse the existing JobDispatcher port. Preserve Celery unchanged. Use a strict
versioned identifier-only message. Use a synthetic HTTP transport in tests and
do not contact Upstash.

Do not add the inbound FastAPI endpoint yet. Do not add provider deployment
workflows.

Run the QStash adapter tests, existing Celery tests, type checking, linting, and
the relevant make check target. Stop after Phase 2. Do not commit.
```

## 6.9 Phase 3 Codex prompt

```text
Implement only Phase 3, signed checkpointed HTTP job execution.

Reuse the application’s existing persisted stages and orchestration. Do not
duplicate the analysis pipeline. Verify QStash signatures using raw request
bytes and current/next signing keys. Add duplicate/concurrent delivery safety
and resolve the checkpoint-committed/next-message-not-published gap.

Use local synthetic signing keys and a fake publisher. Do not contact QStash.
Do not deploy anything.

Add the retry/non-retry response policy from the plan, including the explicit
489 non-retry response for permanently invalid signed payloads.

Run focused API, worker, idempotency, concurrency, and failure-recovery tests.
Run make check. Stop after Phase 3. Do not commit.
```

## 6.10 Phase 4 Codex prompt

```text
Implement only Phase 4, Cloudflare R2 compatibility.

First prove whether the existing boto3-compatible adapter can represent R2
through configuration. Do not create a Cloudflare-specific domain port.

Keep MinIO contract tests passing. Add opt-in live R2 smoke support using
environment variables, but do not require credentials in default CI and do not
contact R2 during ordinary tests.

Document exact R2 CORS and lifecycle configuration without inserting real
account IDs or keys.

Run object-storage contracts and make check. Stop after Phase 4. Do not commit.
```

## 6.11 Phase 5 Codex prompt

```text
Implement only Phase 5, Neon PostgreSQL compatibility.

Reuse the existing SQLAlchemy engine/session/repository implementation. Add a
separate migration URL only if the current configuration cannot safely support
pooled runtime and direct migration connections.

Do not create a Neon-specific repository implementation. Do not contact Neon in
default tests. Add protected opt-in smoke coverage and TLS/configuration tests.

Run migration tests against local PostgreSQL, settings tests, repository tests,
and make check. Stop after Phase 5. Do not commit.
```

## 6.12 Phase 6 Codex prompt

```text
Implement only Phase 6, Render API deployment.

Inspect the real backend Dockerfile and determine its required build context.
Create the deployment workflow/configuration using a protected Render deploy
hook that deploys the exact SHA resolved by the workflow's quality job. Keep
Render auto-deploy disabled, use the backend Docker build root, and wait for
the documented liveness/readiness endpoints.

Do not put real secrets in GitHub workflow YAML.
Do not run migrations automatically at API startup.
Do not start Celery in the alpha API service.

Validate workflow syntax and run repository workflow/config checks. Stop after
Phase 6. Do not commit.
```

## 6.13 Phase 7 Codex prompt

```text
Implement only Phase 7, Cloudflare Pages deployment.

Use Expo static output and the repository’s real pnpm package names/paths.
Use cloudflare/wrangler-action@v3, not cloudflare/pages-action.
Only EXPO_PUBLIC_FABRICASSIST_API_URL and the public environment name may enter
the frontend build.

Add a test or script that scans the generated web bundle for known secret
variable names and common secret prefixes.

Run the static export, frontend tests, typecheck, secret-bundle check, and make
check. Stop after Phase 7. Do not commit.
```

## 6.14 Phase 8 Codex prompt

```text
Implement only Phase 8, alpha CI, deployment, live smoke, and rollback.

Keep routine CI free of external alpha credentials and quota consumption.
Support tag-triggered and manually selected-ref deployment.
Ensure the selected checkout ref is also the Render deploy-hook ref and frontend source.
Order jobs as quality -> migration -> API/web deployment -> post-deploy live
smoke.

Add a separate manual diagnostic live-smoke workflow.
Use workflow_dispatch with a ref input for rollback. Do not move or re-push
published tags.

Reuse existing workflow setup actions and conventions where possible. Do not
upgrade unrelated CI dependencies.

Validate YAML, action inputs, Make targets, and workflow documentation. Stop
after Phase 8. Do not commit.
```

## 6.15 Phase 9 Codex prompt

```text
Implement only Phase 9, alpha runbooks and final local acceptance.

Create the FabricAssist-specific runbooks listed in the plan. Do not copy generic
provider documentation. Include required setup values, validation commands,
failure recovery, quotas, and rollback steps.

Run all deterministic local checks:
- make check;
- make check-alpha-config;
- make test-qstash;
- make build-release-web;
- git diff --check.

Do not attempt to create real Neon, R2, QStash, Render, or Cloudflare resources
and do not request credentials. Clearly list the remaining manual account setup
and live smoke steps. Stop after Phase 9. Do not commit.
```

## 6.16 Review after every phase

Inside the active Codex session:

```text
/review
```

Choose:

```text
Review uncommitted changes
```

Ask for an additional targeted review when needed:

```text
Review the current diff specifically for:
- accidental changes to local Celery behavior;
- secret exposure;
- broken tenant isolation;
- non-idempotent QStash delivery;
- migration incompatibility;
- untested failure paths.
Do not modify files.
```

Then inspect manually:

```bash
git status
git diff --stat
git diff
```

Run the phase checks yourself before committing.

## 6.17 Commit after review

Codex should not commit unless you deliberately delegate that operation.

Recommended manual flow:

```bash
git add <reviewed-files>
git diff --cached
git commit -m "<suggested phase commit>"
```

Confirm cleanliness:

```bash
git status
```

Start a fresh Codex session for the next phase.

## 6.18 Optional non-interactive Codex review

For a read-only automated review:

```bash
codex exec \
  --sandbox read-only \
  "Review the current uncommitted FabricAssist alpha deployment diff. \
Prioritize correctness, security, idempotency, backward compatibility, \
workflow errors, and missing tests. Do not modify files."
```

Do not use unrestricted sandbox mode for this repository.

---

# 7. Merge and release procedure

## Before opening the pull request

```bash
cd ../fabricassist-alpha

git status
make check
make check-alpha-config
make test-qstash
make build-release-web
git diff --check
```

Push:

```bash
git push -u origin feat/free-alpha-deployment
```

Open a pull request to `main`.

## Pull-request requirements

- All deterministic checks pass.
- Existing Celery tests pass.
- MinIO tests pass.
- QStash synthetic tests pass.
- Migration tests pass.
- OpenAPI/client drift is clean.
- Expo static build passes.
- No real credentials are committed.
- No production defaults changed.
- Workflow actions and inputs were verified.
- Live provider setup remains manual and documented.

## After merge

```bash
cd /path/to/fabricassist-platform

git switch main
git pull --ff-only
```

Create the release tag:

```bash
git tag -a v0.1.0-alpha.1 \
  -m "FabricAssist free alpha deployment"

git push origin v0.1.0-alpha.1
```

The deployment workflow must deploy this ref and run live smoke after deployment.

## Remove the worktree

After the branch is merged:

```bash
git worktree remove ../fabricassist-alpha
git branch -d feat/free-alpha-deployment
git worktree prune
```

Keep the release tag. Do not keep a long-lived alpha branch.

---

# 8. Recommended first Codex command

After copying this file to:

```text
docs/alpha/FREE_ALPHA_IMPLEMENTATION_PLAN.md
```

run:

```bash
cd ../fabricassist-alpha

codex \
  --sandbox workspace-write \
  --ask-for-approval on-request
```

Paste the **Phase 0 Codex prompt** first.

Do not begin Phase 1 until you have reviewed:

```text
docs/alpha/implementation-inventory.md
```
