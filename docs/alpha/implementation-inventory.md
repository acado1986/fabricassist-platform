# Free alpha implementation inventory

**Inventory date:** 2026-07-28
**Scope:** Phase 0 only. This records the implementation that exists before the
free-alpha deployment phases; it does not alter runtime behavior.

## Existing execution boundary

There is **no `JobDispatcher` port** in the current codebase, despite the main
implementation plan selecting Celery behind one. The current dispatch boundary
is instead two direct API-to-Celery calls:

| Trigger | Current implementation | Payload |
| --- | --- | --- |
| `POST /v1/scans/{scan_id}/analyse` | `backend/src/fabricassist/api/routes/scans.py` imports `celery_app` inside the handler and calls `send_task("fabricassist.analyse_scan", args=[scan_id], headers={correlation_id})` | scan UUID plus correlation header |
| `POST /v1/scans/{scan_id}/messages` | `backend/src/fabricassist/api/routes/conversations.py` imports `celery_app` inside the handler and calls `send_task("fabricassist.answer_message", args=[message_id], headers={correlation_id})` | message UUID plus correlation header |

The reusable orchestration functions are:

- `fabricassist.application.analysis.analyse_scan(database, storage, settings, scan_id)`;
- `fabricassist.application.conversations.answer_message_by_id(database, message_id, settings)`;
- lifecycle functions in `fabricassist.application.lifecycle` used by the
  retention task.

The Celery composition root is
`backend/src/fabricassist/worker/celery_app.py`. It translates the
product-facing `valkey://` URL to Celery's `redis://` broker URL and configures
late acknowledgement, reject-on-worker-lost, a prefetch multiplier of one, and
900/840 second hard/soft task limits.

`backend/src/fabricassist/worker/tasks.py` is the reusable thin worker entry
layer. Its three `@shared_task` functions are `analyse_scan_task`,
`answer_message_task`, and `process_retention_task`. Analysis and conversation
tasks have `max_retries=3`; only concurrency-gate failures call
`self.retry(..., countdown=30)`. Vision and unexpected analysis failures are
persisted as terminal scan failures before being re-raised.

All direct Celery dependencies found in source are:

- `api/routes/scans.py` — direct import and `send_task` for analysis;
- `api/routes/conversations.py` — direct import and `send_task` for chat;
- `worker/celery_app.py` — `Celery` construction and configuration;
- `worker/tasks.py` — `shared_task` decorators and Celery retry API;
- `infrastructure/telemetry.py` — `CeleryInstrumentor` worker telemetry.

Phase 2 must introduce a port and a Celery adapter, then move the two route
calls to the port. It must not replace the task functions or local Celery
composition root.

## Durable execution state, idempotency, and locks

`backend/src/fabricassist/infrastructure/persistence/models.py` defines the
authoritative `Scan` state. It persists `status`, `progress_percent`,
`analysis_operation_key` (unique), `analysis_attempts`,
`analysis_lease_expires_at`, `analysis_error_code`, and `analysis_stage`.

The observed scan transitions are:

1. `request_analysis` stores `status="queued"`, `analysis_stage="queued"`, and
   `analysis_operation_key` before publishing the Celery task.
2. `analyse_scan` stores `status="processing"`, `analysis_stage="evidence"`,
   and 25% progress before image processing.
3. It completes with `analysis_stage="completed"`, 100% progress, and a status
   derived from deterministic validation (`completed`, `needs_review`, or
   `needs_better_image`).
4. Worker failure handling writes `status="failed"`, `analysis_stage="failed"`,
   an error code, and 100% progress.

There are not yet persisted per-stage checkpoints or continuation cursors.
`analysis_attempts` and `analysis_lease_expires_at` exist on `Scan` but are not
used by the current analysis orchestration. The QStash executor therefore has
durable fields to extend, but cannot reuse an existing checkpoint state machine.

`IdempotencyRecord` is tenant-scoped and has the database uniqueness constraint
`(tenant_id, operation, idempotency_key)`. It is used for image-upload
instructions in `api/routes/scans.py`; the handler compares a request
fingerprint before replaying the stored image ID. Conversation messages have a
separate `(thread_id, idempotency_key)` uniqueness constraint and are replayed
from `api/routes/conversations.py`. Analysis stores an operation key but does
not currently create an `IdempotencyRecord` or protect repeated publishes with a
database transaction/outbox.

No application or repository `SELECT ... FOR UPDATE`, `with_for_update`, or
lease-claim implementation was found for scans. `Scan.version` is stored but
not currently used for optimistic locking. The only active execution lock is
`infrastructure/limits.py`'s Valkey `DistributedConcurrencyGate`, a leased
global-and-tenant concurrency limiter. It is not an authoritative job
idempotency or checkpoint lock. Phase 3 must make duplicate/concurrent QStash
delivery safe in PostgreSQL and reconcile a committed checkpoint whose next
publish fails.

## Object storage

`backend/src/fabricassist/infrastructure/storage/s3.py` provides the one
existing storage adapter, `S3Storage`. It constructs a boto3 S3 client with
`endpoint_url`, `region_name="us-east-1"`, credentials, and
`Config(s3={"addressing_style": "path"})` when
`Settings.s3_force_path_style` is true. It already supports the required S3
operations: private presigned PUT/GET URLs, metadata/image verification,
private reads, and deletes.

`api/routes/scans.py` generates the object key server-side as
`private/{tenant_id}/{scan_id}/{image_id}/original`; no user path is accepted.
`ScanImage` retains object metadata and deletion timestamps in PostgreSQL, while
bytes stay outside PostgreSQL. The current adapter can be configured for an
S3-compatible provider, but it has no R2-specific settings, `auto` region
support, virtual-host configuration, or opt-in live R2 smoke contract yet.

Existing storage coverage is in:

- `backend/tests/integration/test_migrations.py` — local MinIO upload,
  verification, analysis, preview-related API wiring, and deletion paths;
- `backend/tests/unit/test_api.py` — fake storage behavior and error handling;
- `backend/tests/unit/test_production_hardening.py` — production workload
  identity construction.

## Settings and composition roots

`backend/src/fabricassist/settings.py` is the sole typed configuration class:
`Settings(BaseSettings)` reads only `FABRICASSIST_` variables and `.env`. It
currently has `environment: Literal["development", "test", "production"]`,
one `database_url`, mandatory-by-default `valkey_url`, S3 endpoint/credential
settings, vision settings, and production validation. There is no deployment
profile, dispatcher selector, QStash settings, database migration URL, R2
region, or alpha-specific limits.

`backend/src/fabricassist/api/main.py:create_app` is the API composition root.
It builds `Database(settings.database_url)`, `ValkeyRateLimiter`, and
`S3Storage`, stores them on `app.state`, and exposes dependencies through route
overrides. This is the appropriate infrastructure-boundary location for future
dispatcher selection and an internal QStash route; domain and application
modules should remain environment-agnostic.

`backend/src/fabricassist/worker/celery_app.py` is the separate local worker
composition root. Worker task functions instantiate `Settings`, `Database`,
and `S3Storage` at task execution time.

The existing OpenAPI source is the FastAPI app. `make openapi` writes
`docs/api/openapi.json` and runs the frontend generated-client command. Internal
QStash execution must be excluded from the customer client where practical.

## Containers, frontend web output, and migrations

`backend/Dockerfile` requires **`backend/` as Docker build context**: it copies
`pyproject.toml`, `uv.lock`, `README.md`, `alembic.ini`, then `src`,
`migrations`, and `scripts`. Its default command runs only Uvicorn; it does not
start Celery or migrations. The root `docker-compose.yml` starts the API and
the separate `fabricassist-worker` service for local behavior.

`frontend/apps/client/app.config.ts` is the Expo configuration. It currently
uses Metro and `web.output: "single"`; its API URL is read from
`FABRICASSIST_API_PUBLIC_URL`, not the planned
`EXPO_PUBLIC_FABRICASSIST_API_URL`. The frontend workspace's static export is
`pnpm --dir frontend build:web`, implemented as
`pnpm --filter fabricassist-app exec expo export --platform web`. The existing
frontend Docker build is `frontend/Dockerfile` with `frontend/` context.

The normal migration command is `make migrate`, which executes
`alembic -c /app/alembic.ini upgrade head` in the running API container. The
local migration contract command is `make migration-test`, which starts isolated
PostgreSQL and MinIO services and runs `backend/tests/integration`. Alembic
configuration is `backend/alembic.ini`; the migration environment currently
uses the normal `Settings.database_url` rather than a separate migration URL.

## GitHub Actions conventions

The current workflows are `foundation.yml`, `containers.yml`,
`security.yml`, and `release-smoke.yml`. They use `ubuntu-24.04`, explicit
workflow/job concurrency groups, minimal `contents: read` permissions, and
commit-SHA-pinned `actions/checkout` and `actions/upload-artifact` where used.
They install `uv==0.11.2` and activate `pnpm@10.28.2` through Corepack. Existing
CI validates `make check`; the scheduled/manual release smoke creates the local
Compose stack and runs local drills. No alpha provider deployment workflow,
Cloudflare action, Render action, QStash action, or external-alpha credential is
present.

## Tests and commands to reuse

| Phase | Existing tests/commands to extend or preserve |
| --- | --- |
| 1 — typed alpha configuration | `backend/tests/unit/test_settings.py`; `backend/tests/unit/test_production_hardening.py`; `make check` |
| 2 — QStash dispatcher | `backend/tests/unit/test_api.py` for dispatch route behavior; `backend/tests/unit/test_analysis.py` for orchestration; `make check` preserves Celery coverage |
| 3 — signed checkpointed execution | `backend/tests/unit/test_api.py`, `test_analysis.py`, `test_database.py`, and `test_production_hardening.py`; add focused delivery/concurrency/recovery tests |
| 4 — R2 storage | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/test_api.py`, and `test_production_hardening.py`; `make migration-test` exercises MinIO |
| 5 — Neon | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/test_database.py`, `test_settings.py`; `make migration-test` |
| 6 — Render | `.github/workflows/*.yml`, `backend/Dockerfile`, root `Makefile`; validate workflow/config syntax without deployment |
| 7 — Cloudflare Pages | `frontend/apps/client/app.config.ts`, `frontend/package.json`, existing frontend Jest/Playwright suites, and `pnpm --dir frontend build:web` |
| 8 — CI/deployment/smoke/rollback | existing workflow conventions, `Makefile`, `infrastructure/scripts/smoke.sh`, and the deterministic commands introduced by Phases 1–7 |

Current baseline commands are `make check`, `make migration-test`,
`make openapi`, `pnpm --dir frontend build:web`, and `git diff --check`.
The plan's future commands `make check-alpha-config`, `make test-qstash`,
`make test-object-storage`, `make test-migrations`, and `make build-alpha-web`
do not exist yet. The repository uses the singular existing
`make migration-test`, not `make test-migrations`.

## Plan discrepancies and required new code

1. The plan expects a pre-existing `JobDispatcher` port, but the repository has
   none. Phase 2 must create the port/adapters and remove direct API imports;
   Phase 1 cannot merely select a dispatcher in settings.
2. The plan assumes persisted stages/checkpoints and an existing lock; only
   coarse scan stage strings and unused lease fields exist. Phase 3 needs a
   durable checkpoint/claim design and recovery mechanism.
3. `valkey_url` is unconditionally used by API composition for rate limiting
   and by Celery. Alpha QStash selection cannot simply make Valkey optional
   without an intentional rate-limit/composition decision; this is a Phase 1
   design constraint, not a reason to add environment checks to application code.
4. The S3 adapter is compatible in principle, but R2 needs configuration and
   contract coverage; no Cloudflare-specific adapter is currently justified.
5. The database configuration has one URL and no pool/cold-start policy or
   direct migration URL.
6. Expo's existing public API URL variable and single-page web output differ
   from the plan's expected static Pages configuration.
7. No alpha Make targets, provider deployment artifacts, runbooks, or live
   smoke workflow exist yet. They belong only to their respective later phases.

## Recommended implementation order

1. **Phase 1:** Add typed profile/dispatcher configuration at `Settings` and
   composition boundaries, preserving current defaults and tests.
2. **Phase 2:** Create the dispatcher port, preserve a Celery adapter, and add
   a versioned identifier-only QStash publisher with synthetic transport tests.
3. **Phase 3:** Add the authenticated internal execution route plus durable
   checkpoint, idempotency, concurrency, and continuation-publish recovery.
4. **Phases 4–5:** Extend existing S3 and SQLAlchemy configuration for R2 and
   Neon; keep MinIO/PostgreSQL integration contracts as defaults.
5. **Phases 6–8:** Add provider workflows, static web deployment and bundle
   checks, then ordered deployment/smoke/rollback automation.
6. **Phase 9:** Add provider-specific runbooks and execute deterministic local
   acceptance only; real account setup remains manual.

No production code, dependency, migration, workflow, or configuration change
was made for this inventory.
