# ADR-014: Capability adapters and transactional job outbox

- **Status:** Accepted
- **Date:** 2026-07-29

## Context

FabricAssist must preserve the Celery/Valkey AWS and local topology and the
QStash hosted-alpha topology. The alpha implementation selected QStash in scan
routes, Celery bypassed the common message, QStash signing lived in application
code, and cache/rate/concurrency behavior shared concrete Valkey dependencies.
Replacing a technology therefore required business-code changes.

External publication can also fail after a scan is committed as queued. Queue
state cannot be authoritative for whether FabricAssist intended the work.

## Decision

Define independent application ports for job dispatch, hot cache, rate limiting,
concurrency, evidence extraction, care planning, contextual conversation,
object storage, and product information. Infrastructure registries select
adapters from typed `FABRICASSIST_*` settings and inject them at composition
roots. Celery and QStash
receive the same versioned identifier-only analysis message and adapter-specific
redacted configuration. QStash HTTP publication and signed inbound verification
remain infrastructure concerns.

Persist every analysis dispatch intent and correlation ID in PostgreSQL before
external publication. Mark publication only after the adapter succeeds.
Committed-but-unpublished work is republished with a stable deduplication ID;
stage rows, leases, and idempotent execution handle duplicates and worker
crashes.

Conversation user-message rows also persist their original correlation ID and
publication acknowledgement. A bounded API-lifespan reconciler claims
unpublished analysis and conversation intents with `FOR UPDATE SKIP LOCKED` and
republishes them for either Celery or QStash. The API process is the common
runtime in both supported topologies; no unconfigured Celery beat process is
required for recovery.

Business-owned object deletion always creates a PostgreSQL deletion request and
object outbox entry before S3-compatible I/O. Missing objects complete
idempotently, transient failures retry only up to
`FABRICASSIST_DELETION_MAX_ATTEMPTS`, permanent failures are not retried, and
`scan_images.deleted_at` is written only after external deletion succeeds. The
same API-lifespan recovery loop processes these rows in Celery and QStash
topologies.

The frontend session composition root owns one authenticated generated-client
transport. It centralizes API base URL, bearer injection, one refresh retry,
correlation IDs, and shared error-envelope behavior. Presigned object transfer
continues through the web/native `BinaryUpload` adapter.

Celery's broker uses `FABRICASSIST_CELERY_BROKER_URL`, independently from
`FABRICASSIST_VALKEY_URL`. Optional hot cache may use an explicit no-op adapter.
Production rejects no-op rate limiting and concurrency.

## Consequences

- Adding a technology requires an adapter, typed config, registry entry, and
  shared contract tests rather than route/application changes.
- PostgreSQL remains authoritative for intent, checkpoints, and terminal state.
- Celery can move from a Redis-compatible broker to RabbitMQ by configuration.
- Alpha must explicitly configure its no-op capabilities and protected QStash
  credentials.
- Migration `20260729_0018` adds durable `correlation_id` outbox metadata.
- Migration `20260729_0019` adds conversation publication metadata and permits
  image-scoped deletion requests.

## Compatibility and rollback

Both existing topologies remain registered. Rolling back application code
requires downgrading `20260729_0019` and then `20260729_0018`. Existing retained
analysis rows receive a zero-UUID correlation during the 0018 upgrade; existing
conversation rows receive a zero-UUID dispatch correlation during 0019.
Version-1 messages contain no secrets, image bytes, presigned URLs, or provider
payloads.
