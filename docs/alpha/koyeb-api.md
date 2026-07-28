# Koyeb alpha API deployment

Phase 6 deploys the existing FastAPI API as one Koyeb web service. It does not
deploy Celery, Valkey, a migration runner, or a second backend.

## Build and runtime contract

`backend/Dockerfile` copies `pyproject.toml`, `uv.lock`, `README.md`, `src/`,
`migrations/`, and `scripts/` relative to the `backend/` directory. Koyeb must
therefore build with:

```yaml
git-builder: docker
git-workdir: backend
git-docker-dockerfile: Dockerfile
```

The image starts one Uvicorn worker and uses Koyeb's `PORT`, falling back to
`8000` locally. The Koyeb workflow checks `/api/v1/health/live` on port `8000`.
It does not run Alembic, seed data, or Celery at startup.

## One-time Koyeb setup

1. Create the Koyeb application `fabricassist-alpha` in region `fra` and add a
   GitHub repository secret named `KOYEB_API_TOKEN`.
2. Create these Koyeb secrets once; the deployment workflow references them as
   `@NAME` and never writes values to Git:

   ```text
   FABRICASSIST_ACCESS_TOKEN_SECRET
   FABRICASSIST_APP_BASE_URL
   FABRICASSIST_API_PUBLIC_URL
   FABRICASSIST_CORS_ALLOWED_ORIGINS
   FABRICASSIST_DATABASE_URL
   FABRICASSIST_DATABASE_MIGRATION_URL
   FABRICASSIST_S3_ENDPOINT_URL
   FABRICASSIST_S3_PUBLIC_ENDPOINT_URL
   FABRICASSIST_S3_BUCKET
   FABRICASSIST_S3_ACCESS_KEY
   FABRICASSIST_S3_SECRET_KEY
   FABRICASSIST_QSTASH_TOKEN
   FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY
   FABRICASSIST_QSTASH_NEXT_SIGNING_KEY
   FABRICASSIST_QSTASH_DESTINATION_URL
   ```

   `FABRICASSIST_DATABASE_URL` is the pooled Neon URL and
   `FABRICASSIST_DATABASE_MIGRATION_URL` is the direct Neon URL. Both require
   `sslmode=require`. The QStash destination must be the final HTTPS Koyeb API
   URL plus `/internal/jobs/qstash`.
3. Apply Alembic migrations and seed the dedicated alpha tenant through the
   protected migration procedure before the first API deployment. The API
   container intentionally never performs those actions.

The workflow uses the mock vision provider. If a non-mock provider is enabled,
create its provider credential as a Koyeb secret and add its existing typed
setting in a later provider-configuration change; do not place provider keys in
this workflow.

## Validation

Run without contacting Koyeb:

```bash
make check-koyeb-config
```

Phase 8 replaces the independent `main` push deployment with `deploy-alpha.yml`.
It resolves a tag or manually supplied ref once in the `quality` job, then uses
that immutable checkout SHA as Koyeb's `git-sha` and as the frontend checkout.
The deployment order is quality, migration, API/web deployment, then hosted
mock-provider smoke. Rollback is a manual dispatch of that workflow with a
known-good ref; published tags are never moved or re-pushed.
