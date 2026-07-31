# ADR-016: Retire the legacy hosted deployment profile

- **Status:** Accepted
- **Date:** 2026-07-31
- **Supersedes:** The active hosted-profile portions of ADR-013, ADR-014, and ADR-015 remain historical context; their provider-neutral and production topology decisions remain valid.

## Context

The hosted Render, Neon PostgreSQL, Cloudflare R2, Upstash QStash, Cloudflare
Pages, and TLS Valkey topology is now FabricAssist production. Maintaining a
separate executable profile for the former prerelease environment duplicated
configuration, checks, workflows, and operational guidance without providing a
supported deployment target.

## Decision

FabricAssist supports `local` and `production` deployment profiles. The
`development` and `test` environment modes remain available for local Docker
and deterministic tests. The former hosted profile, its template, runtime
settings branch, deployment workflows, active runbooks, and profile-specific
infrastructure path are retired.

Production continues to use independently selected capability adapters and the
same provider-neutral application boundaries: QStash implements `JobDispatcher`,
R2 uses the S3-compatible object-storage adapter, Neon uses PostgreSQL/SQLAlchemy,
Render runs the API container, and Cloudflare Pages hosts the shared Expo
export. No domain or application behavior changes in this decision.

Staging is explicitly deferred. This retirement is not an `alpha` to `staging`
rename and does not create a staging profile, workflow, provider resource, or
credential set. A later staging design must be proposed and reviewed separately.

## Consequences

- Production is the only active hosted deployment path and keeps HTTPS/TLS,
  explicit CORS, protected metrics, fail-closed rate limiting, distributed
  concurrency, QStash signing, private storage, and migration-before-deploy
  validation.
- Local Celery/PostgreSQL/Valkey/MinIO and AWS-compatible shared adapters remain
  supported but inactive in the hosted production composition.
- Historical ADR bodies and retired runbooks remain available under `docs/adr/`
  and `docs/archive/` for audit context; they are not active instructions.
- Retiring the profile changes configuration and operations only. It does not
  change persisted business data, care validation, API contracts, or hosted
  resources.

## External retirement boundary

This ADR does not modify GitHub environments, Render services, Neon databases,
R2 buckets, QStash topics, Pages projects, Valkey instances, credentials, DNS,
or backups. A human operator must inventory and retire any obsolete external
resources only after confirming production isolation, retention obligations,
credential revocation, and rollback/dependency safety.
