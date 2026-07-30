# FabricAssist production deployment

Production uses the same FabricAssist application architecture proven by the
prerelease, but it has separate protected resources and enables the distributed
controls required by the production settings profile.

## Production topology

```text
Cloudflare Pages       Expo web application
Render                 FabricAssist API Docker image
Neon PostgreSQL        Authoritative database and outboxes
Cloudflare R2          Private S3-compatible image storage
Upstash QStash         Signed asynchronous job delivery
TLS Valkey             Hot cache, rate limiting, and concurrency gates
GitHub Actions         Ordered immutable release deployment
```

Do not silently point production at the prerelease database, bucket, smoke account, Render
service, Pages project, or GitHub environment.

## One-time provider setup

1. Create dedicated production Neon pooled runtime and direct migration URLs
   with TLS and backups enabled.
2. Create a private production R2 bucket, restricted application credentials,
   retention/lifecycle rules, and exact production web-origin CORS.
3. Create production QStash credentials and configure its signed destination as
   the production API `/internal/jobs/qstash` HTTPS endpoint.
4. Provision TLS Valkey and configure the production API with its `rediss://`
   URL. Production rejects no-op rate limiting and concurrency.
5. Create a Render production API service from `backend/Dockerfile`, disable
   automatic branch deployment, configure values from
   `.env.production.example`, and create a deploy hook.
6. Create a production Cloudflare Pages project and configure the production
   custom domain.
7. Create a dedicated synthetic production smoke user with no administrative
   privileges.

## Protected GitHub environment

Create a GitHub environment named `production`, require reviewers, prevent
self-review where supported, and restrict deployments to protected stable tags.

Environment variables:

```text
FABRICASSIST_API_URL
FABRICASSIST_PAGES_PROJECT
```

Environment secrets:

```text
FABRICASSIST_DATABASE_MIGRATION_URL
RENDER_DEPLOY_HOOK_URL
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
FABRICASSIST_SMOKE_EMAIL
FABRICASSIST_SMOKE_PASSWORD
```

The Cloudflare token must be scoped only to the production Pages project/account
operations required by the workflow. The Render hook must target only the
production service. Never store runtime database, R2, QStash, Valkey, model, or
JWT secrets in frontend build variables.

## Pre-release validation

```bash
make check
make check-production-config
make check-deployment-workflows
make security-check
pnpm --dir frontend audit --prod --audit-level high
```

The production workflow also builds and scans the API image for fixed
HIGH/CRITICAL vulnerabilities, runs migration and object-storage contracts,
checks OpenAPI drift, and scans the exported frontend for secret markers.

## Release

1. Merge reviewed changes into `main` only after required checks pass.
2. Create one immutable stable tag matching `vMAJOR.MINOR.PATCH`, for example
   `v1.0.0`. Never move or reuse a published tag.
3. `.github/workflows/deploy-production.yml` validates and records the selected
   SHA, applies migrations, deploys API and web, verifies the exact API revision,
   and runs the release smoke.
4. Record the tag, SHA, Alembic head, deployment URLs, operator, and smoke
   outcome without recording credentials or presigned URLs.

Manual deployment is available for a reviewed stable tag or exact commit.
Environment approval remains mandatory.

## Failure and rollback

- A quality or security failure stops before credentials are exposed.
- A migration failure stops API and web deployment. Correct it forward; never
  automatically downgrade the production database.
- An API or web failure leaves the release incomplete. Fix forward or manually
  dispatch the workflow with a known-good immutable ref.
- A smoke failure blocks release acceptance and requires investigation before
  customer traffic is directed to the new revision.
