# FabricAssist environment reference

The files [`.env.example`](../.env.example) and
[`.env.production.example`](../.env.production.example) are safe templates.
They contain placeholders only; copy one to an ignored `.env` file or enter
values in the API/worker provider dashboard. Never put secrets in
`EXPO_PUBLIC_*` variables, the frontend bundle, Git, logs, or support tickets.

## Supported profiles

| Template | Runtime topology | Required services |
| --- | --- | --- |
| `.env.example` | Local Docker and deterministic tests | PostgreSQL, Valkey, MinIO, API, Celery worker |
| `.env.production.example` | Active hosted production | Neon/PostgreSQL, R2, Render API, QStash, TLS Valkey, Cloudflare Pages |

The application reads variables with the `FABRICASSIST_` prefix. Settings are
constructed at the API/worker composition root; routes and application services
do not select providers. Environment variables override values from an ignored
`.env` file.

`development` and `test` are environment modes for the local deployment
profile. They are not hosted deployment profiles. The typed deployment profile
is `local` or `production`.

## Accepted values and defaults

Numeric limits are inclusive. Production values are explicit in
`.env.production.example`; local defaults remain safe for Docker Compose and
deterministic tests.

| Variable | Accepted values / format | Default |
| --- | --- | --- |
| `FABRICASSIST_ENVIRONMENT` | `development`, `test`, `production` | `development` |
| `FABRICASSIST_DEPLOYMENT_PROFILE` | `local`, `production` | `local` |
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
| `FABRICASSIST_RATE_LIMIT_FAIL_OPEN` | `true`, `false` | `true` local, `false` production |
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
| `FABRICASSIST_MERGED_GARMENT_RETENTION_DAYS` | Integer `1..3650` | `30` |
| `FABRICASSIST_UPLOAD_MAX_BYTES` | Positive integer bytes | `12582912` (12 MiB) |
| `FABRICASSIST_UPLOAD_URL_MINUTES` | Integer `1..60` | `10` |
| `FABRICASSIST_MAX_IMAGES_PER_SCAN` | Integer `1..20` | `8` |
| `FABRICASSIST_ANALYSIS_LEASE_MINUTES` | Integer `1..30` | `5` |
| `FABRICASSIST_VISION_TIMEOUT_SECONDS` | Integer `5..120` | `120` |
| `FABRICASSIST_VISION_MAX_INPUT_TOKENS` | Integer `1024..128000` | `128000` |
| `FABRICASSIST_VISION_MAX_OUTPUT_TOKENS` | Integer `256..16000` | `16000` |
| `FABRICASSIST_VISION_DEBUG_LOGGING` | `true`, `false` | `false` |
| `FABRICASSIST_PRODUCT_HTTP_JSON_TIMEOUT_SECONDS` | Integer `1..30` | `10` |
| `FABRICASSIST_PRODUCT_HTTP_JSON_MAX_RESPONSE_BYTES` | Integer `1024..1048576` | `262144` (256 KiB) |
| `FABRICASSIST_PRODUCT_CACHE_MINUTES` | Integer `1..43200` | `1440` |
| `FABRICASSIST_DATABASE_POOL_SIZE` | Integer `1..20` | `5` |
| `FABRICASSIST_DATABASE_MAX_OVERFLOW` | Integer `0..20` | `10` |
| `FABRICASSIST_DATABASE_POOL_RECYCLE_SECONDS` | Integer `-1..3600` (`-1` disables) | `-1` |
| `FABRICASSIST_DATABASE_CONNECT_ATTEMPTS` | Integer `1..5` | `1` |
| `FABRICASSIST_DATABASE_CONNECT_RETRY_SECONDS` | Number `0..30` | `0` |
| `FABRICASSIST_CACHE_HOT_TTL_SECONDS` | Integer `60..604800` | `86400` |

URL, slug, origin, bucket, model, and provider fields are strings subject to
settings validation. Secrets (`*_SECRET`, `*_KEY`, tokens, and passwords) are
required only by the selected adapter and must never be committed.

## URL, TLS, and credential rules

- `FABRICASSIST_APP_BASE_URL`, `FABRICASSIST_API_PUBLIC_URL`, and explicit
  `FABRICASSIST_CORS_ALLOWED_ORIGINS` must use HTTPS in production; `*` is
  rejected.
- `FABRICASSIST_DATABASE_URL` is the pooled runtime PostgreSQL URL and must use
  TLS in production. `FABRICASSIST_DATABASE_MIGRATION_URL` is the direct TLS
  connection used by release migrations.
- `FABRICASSIST_S3_ENDPOINT_URL` and `FABRICASSIST_S3_PUBLIC_ENDPOINT_URL` must
  use HTTPS in production. R2 uses `region=auto` and virtual-host addressing;
  local MinIO may use path-style addressing.
- QStash requires a token, current and next signing keys, and an HTTPS
  `FABRICASSIST_QSTASH_DESTINATION_URL` when selected.
- `FABRICASSIST_GEMINI_API_KEY` is required only when a model capability selects
  Gemini. OpenAI Responses-compatible base URL, API key, and model are required
  only when that adapter is selected.
- The HTTP product adapter requires an HTTPS base URL and explicit host
  allow-list. It must not fetch private, loopback, link-local, credential-bearing,
  oversized, or disallowed redirect targets.
- Production requires enabled, fail-closed rate limiting, real rate-limiter and
  concurrency adapters, TLS Valkey for selected Valkey capabilities, and a
  protected metrics token when metrics are enabled.

## Capability selectors

These variables choose replaceable capabilities independently:

| Variable | Local default | Production value | What it controls |
| --- | --- | --- | --- |
| `FABRICASSIST_JOB_DISPATCHER` | `celery` | `qstash` | Durable analysis/conversation delivery |
| `FABRICASSIST_HOT_CACHE_BACKEND` | `valkey` | `valkey` | Optional transient cache acceleration |
| `FABRICASSIST_RATE_LIMITER_BACKEND` | `valkey` | `valkey` | Request rate-limit counters |
| `FABRICASSIST_CONCURRENCY_GATE_BACKEND` | `valkey` | `valkey` | Distributed execution slots |
| `FABRICASSIST_OBJECT_STORAGE_BACKEND` | `s3` | `s3` | MinIO locally; R2 or AWS S3 remotely |
| `FABRICASSIST_EVIDENCE_PROVIDER` | `mock` | configured independently | Structured image evidence extraction |
| `FABRICASSIST_CARE_PLANNER_PROVIDER` | `mock` | configured independently | Typed care-plan proposal |
| `FABRICASSIST_CHAT_PROVIDER` | `mock` | configured independently | Contextual conversation answers |
| `FABRICASSIST_PRODUCT_INFORMATION_PROVIDER` | `mock` | configured independently | Sourced catalog enrichment |

Unselected adapters do not require their credentials or services. `mock`
providers are deterministic and make no paid or hosted calls. Celery's broker
URL is independent of Valkey cache, rate-limit, and concurrency settings.

## Local setup

```bash
cp .env.example .env
make up
make check-production-config  # validates the committed production template offline
```

Use `make check`, `make test-qstash`, and `make check-deployment-workflows` for
credential-free validation. For hosted operational setup, see
[`production/deployment.md`](production/deployment.md) and
[`production/operations.md`](production/operations.md). Do not source a
committed template directly; configure secrets only in protected settings.
