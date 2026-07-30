# FabricAssist prerelease deployment runbook

This procedure deploys one immutable selected SHA to Render and Cloudflare Pages. Do not create provider resources from CI and do not run migrations at API startup.

## One-time setup and required values

1. Create an empty dedicated Neon prerelease database. Store pooled runtime and direct migration `postgresql+psycopg://...?...sslmode=require` URLs.
2. Apply the existing Alembic head through the direct URL and seed the prerelease tenant/administrator. Record the migration head.
3. Create private R2 bucket `fabricassist-alpha`, an application-only R2 key, exact Pages CORS origin, and a `private/` lifecycle rule of at least seven days. Use `S3_REGION=auto` and virtual-host addressing.
4. Create QStash credentials; retain both current and next signing keys.
5. Create the Render `fabricassist-alpha` Docker web service in Frankfurt, set the Render runtime variables in [secrets.md](secrets.md), disable auto-deploy, and configure the API public URL.
6. Add the Render deploy-hook URL as the protected GitHub `RENDER_DEPLOY_HOOK_URL` secret. Deploy Render with the release workflow; then set its final HTTPS internal QStash destination and verify a signed synthetic delivery.
7. Create Pages project `fabricassist-alpha`, deploy the static Expo output, and add the exact final Pages origin (no wildcard, no trailing slash) to both API `FABRICASSIST_CORS_ALLOWED_ORIGINS` and R2 CORS.

The concrete R2 values and lifecycle contract are in [r2-storage.md](r2-storage.md); Neon values are in [neon-database.md](neon-database.md). Do not replace these with generic provider tutorials.

## Pre-deployment gate

```bash
make check
make check-alpha-config
make test-qstash
make build-release-web
git diff --check
```

In GitHub, `release-quality.yml` additionally runs `make test-migrations`, `make test-object-storage`, and `make check-openapi-drift`. A failure is a release stop: fix the repository failure or configuration mismatch, rerun the local checks, and do not dispatch deployment merely to diagnose it.

## Deploy and record

1. Merge the reviewed change, then create and push a new immutable prerelease
   tag such as `v0.1.0-alpha.29`. Never move or re-push a published
   tag. Stable tags use the separate
   [production deployment workflow](../production/deployment.md).
2. Let `deploy-prerelease.yml` run, or dispatch it with a known exact tag/commit in `ref`. The workflow runs quality, migrates, deploys API and web from its recorded SHA, then executes hosted mock smoke.
3. Record in the release log: selected SHA, tag, Alembic head, API origin, Pages origin, date/operator, and smoke outcome. Do not record secrets, presigned URLs, access tokens, or image data.
4. Run the full post-deploy checklist in [smoke-tests.md](smoke-tests.md).

## Failure recovery

- **Migration failure:** the deployment runner retries only transient managed-PostgreSQL connection shutdowns up to four times with bounded backoff. A schema/configuration failure still stops before API/web deployment; correct it with forward-compatible remediation, then rerun the same release process. Never automatically downgrade Neon.
- **API/web deployment failure:** confirm the selected SHA in workflow output, correct configuration or workflow failure, then redeploy that SHA. Do not deploy a different unreviewed checkout.
- **QStash destination failure:** pause new prerelease analysis dispatch if message compatibility is affected; fix the exact HTTPS destination/signing keys, send a synthetic signed delivery, and let recovery reconcile durable pending checkpoints before reopening traffic.
- **Smoke failure after deployment:** keep the release unaccepted, follow [troubleshooting](troubleshooting.md), then either fix-forward or execute [rollback](rollback.md).
