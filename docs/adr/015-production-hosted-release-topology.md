# ADR-015: Production hosted release topology

- **Status:** Accepted
- **Date:** 2026-07-30

## Context

The free alpha proved the provider-neutral application architecture on Render,
Cloudflare Pages, Neon PostgreSQL, Cloudflare R2, and QStash. FabricAssist now
needs a stable production release path without reintroducing a second
application implementation or weakening production security requirements.
Alpha uses no-op hot-cache, rate-limit, and concurrency adapters because of its
cost constraints, but those adapters are forbidden in production.

## Decision

Production uses the same container and application boundaries as alpha with
separate production resources and credentials:

- the API Docker image runs on a dedicated Render production service;
- the Expo web export runs on a dedicated Cloudflare Pages project;
- Neon PostgreSQL remains authoritative and migrations run before deployment;
- private Cloudflare R2 remains behind the S3-compatible storage adapter;
- QStash delivers signed asynchronous job stages; and
- a TLS Valkey service provides the hot cache, fail-closed rate limiter, and
  distributed concurrency gate required by the production profile.

Stable `vMAJOR.MINOR.PATCH` tags trigger `.github/workflows/deploy-production.yml`.
The workflow records one immutable source SHA, runs quality/security gates,
applies forward migrations, deploys API and web from that SHA, verifies the API
revision, and completes a production smoke. Production secrets and variables
belong to a protected GitHub `production` environment and never reuse the
alpha environment as an authorization boundary.

## Consequences

- Alpha and production share code and release utilities but have separate
  workflows, provider resources, databases, buckets, user accounts, and secret
  boundaries.
- A stable tag cannot deploy successfully until the production GitHub
  environment and provider resources described in the runbook exist.
- Production incurs the additional operational cost of TLS Valkey and dedicated
  provider resources.
- Rollback redeploys a known-good immutable ref; database migrations are not
  automatically downgraded.
- Moving to Celery/Valkey workers, AWS, or a self-hosted Compose topology remains
  possible through the existing adapters and requires a later deployment ADR,
  not domain changes.
