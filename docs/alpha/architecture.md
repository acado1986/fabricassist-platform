# FabricAssist alpha architecture

The alpha is the existing FabricAssist modular monolith, not a hosted fork. The API remains the `fabricassist-api` FastAPI container; local `fabricassist-worker` continues to run the Celery implementation. Only the infrastructure adapter selected at the composition boundary changes.

```text
Cloudflare Pages (Expo static app)
  -> Koyeb FabricAssist API
     -> private R2 presigned image objects
     -> Neon PostgreSQL (authoritative scans/checkpoints/results)
     -> QStash signed, identifier-only continuation messages
```

## Release profile

| Concern | Alpha selection | Local/future compatibility |
| --- | --- | --- |
| Dispatcher | `qstash`; signed `/internal/jobs/qstash` delivery | Celery dispatcher and worker stay supported |
| Database | Neon pooled runtime URL; direct Alembic URL | Existing SQLAlchemy/PostgreSQL path |
| Object storage | R2 through existing `S3Storage` | MinIO path-style and AWS S3 remain supported |
| Web | Expo static export on Pages | Existing shared Expo app |
| AI smoke | deterministic `mock` provider | Live providers remain opt-in |

QStash payloads contain a schema version plus identifiers only. The internal endpoint verifies raw request bytes and the exact configured destination using current/next signing keys. PostgreSQL keeps durable stage/checkpoint state and the executor handles duplicate deliveries; neither QStash nor R2 is a system of record.

## Boundaries to preserve

- Do not expose the internal QStash endpoint through the generated customer API client.
- Browser clients use only short-lived scoped R2 presigned URLs, never R2 credentials or bucket listing permissions.
- Koyeb starts one Uvicorn worker, not Celery or Alembic. Migrations run before API deployment using the selected ref's direct Neon URL.
- Build-time web variables are only `EXPO_PUBLIC_FABRICASSIST_API_URL` and `EXPO_PUBLIC_FABRICASSIST_ENVIRONMENT`.
