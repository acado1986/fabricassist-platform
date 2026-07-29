# FabricAssist environment reference

The files [`.env.example`](../.env.example) and
[`.env.alpha.example`](../.env.alpha.example) are safe templates. They contain
placeholders only; copy one to an ignored `.env` file or enter the values in the
API/worker provider dashboard. Never put secrets in `EXPO_PUBLIC_*` variables,
the frontend bundle, Git, logs, or support tickets.

## Which template should I use?

| Template | Runtime topology | Required services |
| --- | --- | --- |
| `.env.example` | Local Docker (also matches the AWS/Celery shape) | PostgreSQL, Valkey, MinIO, API, Celery worker |
| `.env.alpha.example` | Hosted free alpha | Neon/PostgreSQL, R2, Render API, QStash |

The application reads variables with the `FABRICASSIST_` prefix. Settings are
constructed at the API/worker composition root; routes and application services
do not select providers. Environment variables override values from an ignored
`.env` file.

## Capability selectors

These variables choose replaceable infrastructure capabilities. They are not
interchangeable:

| Variable | Local default | Alpha value | What it controls |
| --- | --- | --- | --- |
| `FABRICASSIST_JOB_DISPATCHER` | `celery` | `qstash` | Durable analysis/conversation delivery. |
| `FABRICASSIST_CELERY_BROKER_URL` | Valkey Redis URL | unused | Celery's independent broker; it may be replaced by RabbitMQ without changing Valkey cache settings. |
| `FABRICASSIST_HOT_CACHE_BACKEND` | `valkey` | `noop` | Optional transient evidence hot-cache acceleration. PostgreSQL remains authoritative. |
| `FABRICASSIST_RATE_LIMITER_BACKEND` | `valkey` | `noop` | Request rate-limit counters. Production must use a real limiter. |
| `FABRICASSIST_CONCURRENCY_GATE_BACKEND` | `valkey` | `noop` | Distributed analysis/conversation execution slots. Alpha uses `noop` because it has no Valkey service. |
| `FABRICASSIST_OBJECT_STORAGE_BACKEND` | `s3` | `s3` | S3-compatible private object storage: MinIO locally, AWS S3 or R2 remotely. |
| `FABRICASSIST_EVIDENCE_PROVIDER` | `mock` | `mock` | Structured image evidence extraction. |
| `FABRICASSIST_CARE_PLANNER_PROVIDER` | `mock` | `mock` | Typed care-plan proposal. |
| `FABRICASSIST_CHAT_PROVIDER` | `mock` | `mock` | Contextual conversation answers. |
| `FABRICASSIST_PRODUCT_INFORMATION_PROVIDER` | `mock` | `mock` | Optional product/catalog enrichment. |

`mock` providers are deterministic and make no paid or hosted calls. Gemini and
OpenAI Responses are opt-in and require the corresponding adapter-specific
credentials and model settings.

## Core groups

### Runtime and API

- `FABRICASSIST_ENVIRONMENT` and `FABRICASSIST_DEPLOYMENT_PROFILE` identify the
  safety policy (`development/local`, `alpha`, or `production`).
- `FABRICASSIST_API_PUBLIC_URL`, `FABRICASSIST_APP_BASE_URL`, and
  `FABRICASSIST_CORS_ALLOWED_ORIGINS` describe browser/device origins. Alpha and
  production must use HTTPS and explicit origins.
- `FABRICASSIST_ACCESS_TOKEN_SECRET` signs access tokens. It is a secret and
  must be replaced outside isolated local development.

### PostgreSQL and Valkey

- `FABRICASSIST_DATABASE_URL` is the runtime PostgreSQL connection.
- `FABRICASSIST_DATABASE_MIGRATION_URL` is the direct administrative migration
  connection used by alpha migrations.
- `FABRICASSIST_VALKEY_URL` is used only by selected Valkey adapters.
- `FABRICASSIST_CELERY_BROKER_URL` is independent from `VALKEY_URL`.

PostgreSQL stores scans, revisions, conversations, outboxes, checkpoints, and
durable cache records. Valkey is acceleration/coordination infrastructure only.

### Object storage and uploads

`FABRICASSIST_S3_ENDPOINT_URL` is the server endpoint;
`FABRICASSIST_S3_PUBLIC_ENDPOINT_URL` is used when generating browser-reachable
presigned URLs. `FABRICASSIST_S3_BUCKET`, `FABRICASSIST_S3_REGION`, and
`FABRICASSIST_S3_FORCE_PATH_STYLE` identify the S3-compatible bucket. Local
MinIO uses path-style addressing; R2 uses `region=auto` and virtual-host style.

`FABRICASSIST_S3_ACCESS_KEY` and `FABRICASSIST_S3_SECRET_KEY` are optional when
AWS workload identity is configured, and are always secret. Upload limits and
presign lifetime are controlled by `FABRICASSIST_UPLOAD_MAX_BYTES` and
`FABRICASSIST_UPLOAD_URL_MINUTES`.

### Jobs and recovery

- `FABRICASSIST_JOB_STAGE_BUDGET_SECONDS` bounds one analysis checkpoint.
- `FABRICASSIST_PUBLICATION_RECOVERY_INTERVAL_SECONDS` and
  `FABRICASSIST_PUBLICATION_RECOVERY_BATCH_SIZE` control the PostgreSQL outbox
  recovery loop.
- `FABRICASSIST_DELETION_MAX_ATTEMPTS` bounds transient object-deletion retries.
- QStash token/signing keys and destination URL are required only for the
  QStash topology and belong in protected provider settings.

### Model and product adapters

The three model selectors are independent, so evidence, planning, and chat may
be changed separately. Provider-specific values remain grouped by adapter:

- Gemini: `FABRICASSIST_GEMINI_API_KEY`, `FABRICASSIST_GEMINI_MODEL`.
- OpenAI Responses-compatible gateway:
  `FABRICASSIST_OPENAI_RESPONSES_BASE_URL`, `..._API_KEY`, `..._MODEL`, and
  `..._EXTRA_HEADERS_JSON`.
- HTTP product catalog: `FABRICASSIST_PRODUCT_HTTP_JSON_BASE_URL`,
  `..._ALLOWED_HOSTS`, `..._API_KEY`, timeout, and response-size limits.

Product information is optional enrichment. Catalog outages never weaken
photographed-label safety rules.

## Safe setup examples

```bash
# Local Docker
cp .env.example .env
make up

# Hosted alpha: configure .env.alpha.example values in Render/GitHub secrets;
# do not run `source .env.alpha.example` because it is a documentation template.
make check-alpha-config
```

After changing adapter selectors, restart the API and worker. For alpha, save
the values in Render before running the protected live smoke; changing the
repository example alone does not change Render's environment.
