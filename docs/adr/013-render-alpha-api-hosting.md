# ADR-013: Use Render for free-alpha API hosting

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The free-alpha plan initially selected Koyeb for the single FastAPI API service.
The alpha must remain a deployment profile of the existing modular monolith,
retain Celery/Valkey/MinIO locally, use a selected immutable source SHA for
release and rollback, and keep runtime credentials outside the repository.

The operator selected Render's Docker web-service offering in Frankfurt with
auto-deploy disabled. Render provides a Git-backed Docker service and a
restricted deploy hook that can deploy an explicitly supplied commit SHA.

## Decision

Use Render, not Koyeb, for the alpha `fabricassist-api` service. The existing
`backend/Dockerfile` remains the build artifact with `backend/` as its build
root. Render runs one Uvicorn worker, receives its runtime settings only from
the Render dashboard, and never runs Celery, Alembic, or seed logic at startup.

The protected GitHub deployment workflow uses the `RENDER_DEPLOY_HOOK_URL`
secret and sends the SHA resolved by its quality job as the deploy hook `ref`
query parameter.
It waits for liveness and readiness before allowing hosted smoke. Migrations
continue to run first from GitHub against the direct Neon URL.

## Consequences

- The Koyeb workflow/action, secret contract, configuration checks, and
  runbooks are replaced by Render equivalents.
- The GitHub deploy-hook URL is a secret with permission only to trigger the
  configured Render service; it is not embedded in files or logs.
- Auto-deploy remains disabled so a selected-SHA release is not superseded by
  an unreviewed branch head.
- Rollback remains a selected known-good ref deployment and never downgrades
  PostgreSQL automatically.
- The local Celery/Valkey/MinIO and future AWS deployment paths are unchanged.
