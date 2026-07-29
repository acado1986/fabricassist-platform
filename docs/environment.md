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

## Accepted values and defaults

The backend settings model accepts the following values. Numeric limits are
inclusive. Alpha applies the smaller pool and image limits shown below.

| Variable | Accepted values / format | Default |
| --- | --- | --- |
| `FABRICASSIST_ENVIRONMENT` | `development`, `test`, `alpha`, `production` | `development` |
| `FABRICASSIST_DEPLOYMENT_PROFILE` | `local`, `alpha`, `production` | `local` |
| `FABRICASSIST_JOB_DISPATCHER` | `celery`, `qstash` | `celery` |
| `FABRICASSIST_HOT_CACHE_BACKEND` | `valkey`, `noop` | `valkey` |
| `FABRICASSIST_RATE_LIMITER_BACKEND` | `valkey`, `noop` | `valkey` |
| `FABRICASSIST_CONCURRENCY_GATE_BACKEND` | `valkey`, `noop` | `valkey` |
| `FABRICASSIST_OBJECT_STORAGE_BACKEND` | `s3` | `s3` |
| `FABRICASSIST_EVIDENCE_PROVIDER` | `mock`, `gemini`, `openai_responses` | `mock` |
| `FABRICASSIST_CARE_PLANNER_PROVIDER` | `mock`, `gemini`, `openai_responses` | `mock` |
| `FABRICASSIST_CHAT_PROVIDER` | `mock`, `gemini`, `openai_responses` | `mock` |
| `FABRICASSIST_PRODUCT_INFORMATION_PROVIDER` | `mock`, `http_json` | `mock` |
| `FABRICASSIST_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `FABRICASSIST_ACCESS_TOKEN_MINUTES` | Integer `5..60` | `15` |
| `FABRICASSIST_REFRESH_TOKEN_DAYS` | Integer `1..90` | `14` |
| `FABRICASSIST_SECURITY_HSTS_SECONDS` | Integer `0..63072000` | `31536000` |
| `FABRICASSIST_METRICS_ENABLED` | `true`, `false` | `true` |
| `FABRICASSIST_RATE_LIMIT_ENABLED` | `true`, `false` | `true` |
| `FABRICASSIST_RATE_LIMIT_FAIL_OPEN` | `true`, `false` | `true` local, `false` alpha |
| `FABRICASSIST_RATE_LIMIT_GLOBAL_PER_MINUTE` | Integer `1..100000` | `600` |
| `FABRICASSIST_RATE_LIMIT_AUTH_PER_MINUTE` | Integer `1..10000` | `10` |
| `FABRICASSIST_RATE_LIMIT_ANALYSIS_PER_MINUTE` | Integer `1..10000` | `10` |
| `FABRICASSIST_RATE_LIMIT_CHAT_PER_MINUTE` | Integer `1..10000` | `20` |
| `FABRICASSIST_CONVERSATION_RECENT_MESSAGE_LIMIT` | Integer `1..100` | `12` |
| `FABRICASSIST_CONVERSATION_RELEVANT_IMAGE_LIMIT` | Integer `1..20` | `8` |
| `FABRICASSIST_WORKER_GLOBAL_CONCURRENCY` | Integer `1..1000` | `8` |
| `FABRICASSIST_WORKER_TENANT_CONCURRENCY` | Integer `1..100` | `2` |
| `FABRICASSIST_WORKER_CONCURRENCY_LEASE_SECONDS` | Integer `30..3600` | `300` |
| `FABRICASSIST_VISION_MAX_CONCURRENCY` | Integer `1..100` | `1` |
| `FABRICASSIST_JOB_STAGE_BUDGET_SECONDS` | Integer `1..900` | `75` |
| `FABRICASSIST_PUBLICATION_RECOVERY_INTERVAL_SECONDS` | Integer `5..3600` | `30` |
| `FABRICASSIST_PUBLICATION_RECOVERY_BATCH_SIZE` | Integer `1..1000` | `100` |
| `FABRICASSIST_DELETION_MAX_ATTEMPTS` | Integer `1..100` | `5` |
| `FABRICASSIST_DEFAULT_IMAGE_RETENTION_DAYS` | Integer `1..365` | `7` |
| `FABRICASSIST_UPLOAD_MAX_BYTES` | Positive integer bytes | `12582912` (12 MiB) |
| `FABRICASSIST_UPLOAD_URL_MINUTES` | Integer `1..60` | `10` |
| `FABRICASSIST_MAX_IMAGES_PER_SCAN` | Integer `1..20` (`1..3` alpha) | `8` (`3` alpha) |
| `FABRICASSIST_ANALYSIS_LEASE_MINUTES` | Integer `1..30` | `5` |
| `FABRICASSIST_VISION_TIMEOUT_SECONDS` | Integer `5..120` | `120` |
| `FABRICASSIST_VISION_MAX_INPUT_TOKENS` | Integer `1024..128000` | `128000` |
| `FABRICASSIST_VISION_MAX_OUTPUT_TOKENS` | Integer `256..16000` | `16000` |
| `FABRICASSIST_VISION_DEBUG_LOGGING` | `true`, `false` | `false` |
| `FABRICASSIST_PRODUCT_HTTP_JSON_TIMEOUT_SECONDS` | Integer `1..30` | `10` |
| `FABRICASSIST_PRODUCT_HTTP_JSON_MAX_RESPONSE_BYTES` | Integer `1024..1048576` | `262144` (256 KiB) |
| `FABRICASSIST_PRODUCT_CACHE_MINUTES` | Integer `1..43200` | `1440` |
| `FABRICASSIST_DATABASE_POOL_SIZE` | Integer `1..20` | `5` (`2` alpha) |
| `FABRICASSIST_DATABASE_MAX_OVERFLOW` | Integer `0..20` | `10` (`1` alpha) |
| `FABRICASSIST_DATABASE_POOL_RECYCLE_SECONDS` | Integer `-1..3600` (`-1` disables) | `-1` (`300` alpha) |
| `FABRICASSIST_DATABASE_CONNECT_ATTEMPTS` | Integer `1..5` | `1` (`3` alpha) |
| `FABRICASSIST_DATABASE_CONNECT_RETRY_SECONDS` | Number `0..30` | `0` (`1` alpha) |
| `FABRICASSIST_CACHE_HOT_TTL_SECONDS` | Integer `60..604800` | `86400` |

URL, slug, origin, bucket, model, and provider fields are strings subject to
deployment safety checks. Secrets (`*_SECRET`, `*_KEY`, tokens, and passwords)
must never be committed and are required only by the selected adapter.

String and secret fields use these formats:

- `FABRICASSIST_ACCESS_TOKEN_SECRET`: at least 32 characters; replace the local
  placeholder outside development.
- `FABRICASSIST_DEFAULT_TENANT_SLUG`: non-empty slug, at least 3 characters.
- `FABRICASSIST_APP_BASE_URL`, `FABRICASSIST_API_PUBLIC_URL`, and
  `FABRICASSIST_OTEL_EXPORTER_OTLP_ENDPOINT`: URLs; alpha/production public URLs
  must use HTTPS. The OTLP URL may be empty.
- `FABRICASSIST_CORS_ALLOWED_ORIGINS`: comma-separated explicit origins; alpha
  and production require HTTPS origins and reject `*`.
- `FABRICASSIST_DATABASE_URL` and `FABRICASSIST_DATABASE_MIGRATION_URL`:
  PostgreSQL URLs. Alpha requires `sslmode=require` and a separate migration URL.
- `FABRICASSIST_VALKEY_URL` and `FABRICASSIST_CELERY_BROKER_URL`: Redis/Valkey
  or AMQP broker URLs; the latter is required only for Celery.
- `FABRICASSIST_S3_ENDPOINT_URL`, `FABRICASSIST_S3_PUBLIC_ENDPOINT_URL`,
  `FABRICASSIST_S3_REGION`, `FABRICASSIST_S3_BUCKET`: S3-compatible connection
  values. Alpha requires HTTPS, `region=auto`, and non-local bucket values.
- `FABRICASSIST_QSTASH_TOKEN`, `FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY`,
  `FABRICASSIST_QSTASH_NEXT_SIGNING_KEY`, and
  `FABRICASSIST_QSTASH_DESTINATION_URL`: required for `qstash`; destination must
  be HTTPS.
- `FABRICASSIST_GEMINI_API_KEY` and `FABRICASSIST_GEMINI_MODEL`: Gemini
  credentials/model; the key is required only when a capability selects Gemini.
- `FABRICASSIST_OPENAI_RESPONSES_BASE_URL`, `..._API_KEY`, `..._MODEL`, and
  `..._EXTRA_HEADERS_JSON`: Responses-compatible endpoint, credentials, model,
  and valid JSON headers; required only when selected.
- `FABRICASSIST_PRODUCT_HTTP_JSON_BASE_URL`, `..._API_KEY`, and
  `..._ALLOWED_HOSTS`: HTTPS catalog endpoint, optional credential, and a
  comma-separated host allow-list; required when the product provider is
  `http_json`.
- `FABRICASSIST_METRICS_ACCESS_TOKEN`: optional bearer token for metrics.

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
be changed separately. Product information is a different capability and is
not a Gemini/OpenAI model selector: it supports only `mock` or `http_json`.
Provider-specific values remain grouped by adapter:

`FABRICASSIST_VISION_PROVIDER` is a deprecated pre-capability setting. It is no
longer read; configure `FABRICASSIST_EVIDENCE_PROVIDER` instead.

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
