# Render prerelease API deployment

Phase 6 deploys the existing FastAPI API as one Render Docker web service. It
does not deploy Celery, Valkey, a migration runner, or a second backend.

## Build and runtime contract

Configure the Render service with root directory `backend` and Dockerfile path
`Dockerfile`. The Dockerfile copies its build inputs relative to that directory.
It starts one Uvicorn worker and honors Render's `PORT`, falling back to `8000`
locally. Configure the Render health check as `/api/v1/health/live`.

Do not configure a Render pre-deploy migration command: the protected GitHub
migration job uses the direct Neon URL before API deployment. Do not put
credentials in Docker build arguments.

## One-time Render setup

1. Create the `fabricassist-alpha` Docker web service in Frankfurt, connected
   to the approved repository. Disable auto-deploy.
2. In Render's dashboard, set the runtime variables listed in
   [`secrets.md`](secrets.md). The runtime database URL is the pooled Neon TLS
   URL; the migration URL is the direct TLS URL. Do not place either in source.
3. Set the final HTTPS API URL in `FABRICASSIST_APP_BASE_URL` and
   `FABRICASSIST_API_PUBLIC_URL`. Set
   `FABRICASSIST_QSTASH_DESTINATION_URL` to
   `https://<final-api-origin>/internal/jobs/qstash` only after that origin is
   live.
4. Create a Render deploy hook for this service and add its complete URL only as
   the protected GitHub `RENDER_DEPLOY_HOOK_URL` secret. This URL is secret and
   must not be pasted into logs, issues, shell history, or repository files.

The deployment workflow sends the selected immutable SHA as the hook's `ref`
query parameter.
Render must remain configured with auto-deploy disabled. The workflow waits for
liveness and readiness; it never starts Celery or runs Alembic in the API
container.

## Validation

Run without contacting Render:

```bash
make check-render-config
```
