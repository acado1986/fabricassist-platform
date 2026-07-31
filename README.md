# FabricAssist

FabricAssist is a safety-oriented clothing-care assistant for garment owners and
professional cleaning companies. The approved target analyses multiple garment,
label, barcode/brand, stain, damage, and construction images; builds sourced
structured evidence; lets AI propose rich care guidance; and releases actionable
claims only after deterministic Python validation. It also remembers physical
garments, service history, sourced product data, and contextual conversations.

> **Implementation status — Phase 19:** authenticated users can collect up to
> eight typed photos, queue revision-aware analysis, and view validator-gated,
> localized care guidance. Physical-garment history is separate from product data.
> The local mock never calls a paid provider or external catalog: it returns
> review-safe evidence and a deterministic fixture catalog for checksum-valid
> entered or OCR-located barcode digits. Product matches are displayed with their
> source, match status, and retrieval time; they do not link garment history or
> override photographed care-label facts. Catalog lookups are cached durably for
> `FABRICASSIST_PRODUCT_CACHE_MINUTES` (one day by default); a user can invalidate
> their scan's cached lookup with an auditable reason. The optional HTTP JSON
> adapter requires an HTTPS allow-list and rejects private addresses, redirects,
> non-JSON, and oversized responses. Live catalog use remains opt-in pending
> source licensing, privacy, and outbound-network review.

Phase 19 adds OTLP tracing, Prometheus-compatible process and durable business
metrics, redacted structured logs, explicit security headers/CORS, Valkey-backed
rate and provider-concurrency limits, an optional Grafana stack, deployment
infrastructure, supply-chain CI, backup/restore and failure drills,
bounded load gates, and web/native release procedures. The garment-intelligence
cutover is complete; there is no fixed two-photo or `decide_care()` fallback.

Infrastructure is selected independently by capability at backend composition
roots. Local defaults use Celery plus Valkey-backed hot cache, rate limiting,
and concurrency; production uses QStash plus TLS Valkey for those capabilities.
`FABRICASSIST_CELERY_BROKER_URL` is independent from
`FABRICASSIST_VALKEY_URL`, so RabbitMQ can replace the Celery broker without
changing application code. PostgreSQL remains authoritative for job intent,
checkpoints, results, and durable caches.

## Sources of truth

Read these documents before making changes, in the precedence described by
[`AGENTS.md`](AGENTS.md):

- [Product and technical requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Environment variable reference](docs/environment.md)
- [Production deployment runbook](docs/production/deployment.md)
- [Production operations](docs/production/operations.md)
- [Documentation index](docs/README.md)
- [Next-session garment-intelligence prompt](docs/prompts/IMPLEMENT_GARMENT_INTELLIGENCE.md)

The three source documents intentionally remain under `docs/`; they must not be
duplicated at the repository root.

## Planned repository structure

```text
.
├── AGENTS.md
├── README.md
├── Makefile
├── docker-compose.yml
├── backend/                  # Python namespace will be fabricassist
├── frontend/                 # Expo application will be fabricassist-app
├── infrastructure/           # Local orchestration and later deployment assets
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── adr/
│   ├── production/
│   ├── archive/
│   ├── prompts/
│   └── runbooks/
└── .github/workflows/
```

The backend uses `backend/src/fabricassist/`, with `fabricassist.api` and a
separate `fabricassist.worker` process. The Expo application is
`frontend/apps/client` (`fabricassist-app`) with typed `es`/`en` catalogs.

## Prerequisites

Phase 3 requires:

- Git and GNU Make
- Docker Engine with Docker Compose v2
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22+ with Corepack and pnpm 10

Both backend and frontend lockfiles are initialized. The Expo app is a
development shell only; use a development build for native work.

## Local environment

```bash
cp .env.example .env
make bootstrap
```

`.env.example` contains development-only placeholders. Change every value marked
for replacement before using any shared or production environment.
Never commit `.env` or real credentials.

See the complete [environment variable reference](docs/environment.md) for the
purpose of each setting, the local Docker and production topologies, and the
capability selectors. The examples are
templates, not files to source directly.

Capability selection examples:

```bash
# Local/AWS worker topology
FABRICASSIST_JOB_DISPATCHER=celery
FABRICASSIST_CELERY_BROKER_URL=redis://fabricassist-valkey:6379/0
FABRICASSIST_HOT_CACHE_BACKEND=valkey
FABRICASSIST_RATE_LIMITER_BACKEND=valkey
FABRICASSIST_CONCURRENCY_GATE_BACKEND=valkey

# Production topology (QStash credentials remain protected secrets)
FABRICASSIST_JOB_DISPATCHER=qstash
FABRICASSIST_HOT_CACHE_BACKEND=valkey
FABRICASSIST_RATE_LIMITER_BACKEND=valkey
FABRICASSIST_CONCURRENCY_GATE_BACKEND=valkey
```

Production startup rejects no-op rate limiting and concurrency. Routes, domain
rules, and application services never select a concrete technology.

## Commands currently available

| Command | Current behavior |
|---|---|
| `make bootstrap` | Synchronizes locked backend and frontend dependencies. |
| `make up` | Starts PostgreSQL/pgvector, Valkey, MinIO, the API, and the analysis worker. |
| `make start` | Starts the local backend stack, then launches the Expo web client. |
| `make down` / `make logs` | Stops or follows the Compose project. |
| `make smoke` | Verifies service health, private bucket access, and API liveness. |
| `make reset-local CONFIRM=1` | Removes only FabricAssist local volumes after an explicit guard. |
| `make migrate` / `make seed` | Applies schema migrations and creates the development tenant. |
| `make migration-test` | Runs Phase 5 migrations against isolated Compose PostgreSQL. |
| `make test` | Runs foundation checks plus backend and frontend unit tests. |
| `make lint` | Runs configuration validation, Ruff/Pyright, Prettier, ESLint, and TypeScript. |
| `make openapi` | Regenerates `docs/api/openapi.json` and the read-only frontend API client. |
| `make check` | Runs the complete default local quality gate. |
| `make observability-up` | Starts OTEL Collector, Prometheus, and Grafana on the optional profile. |
| `make backup-restore-test` | Restores a PostgreSQL backup into an isolated drill database. |
| `make load-test` | Runs a bounded readiness load smoke with p95/error-rate gates. |
| `make security-check` / `make iac-check` | Runs local hardening checks and validates OpenTofu. |
| `make release-check` | Runs all non-cloud release gates available on the host. |

`make migrate` applies all schema migrations through the running API container.
`make seed` creates the idempotent development tenant required by public local registration.
`make migration-test` runs empty-upgrade, downgrade/upgrade, metadata, and seed
idempotency checks against the isolated Compose PostgreSQL service.

### API and local processing

After `make up`, the API includes:

- health endpoints under `/api/v1/health/`;
- authenticated draft scan creation, typed multi-photo collection (up to
  `FABRICASSIST_MAX_IMAGES_PER_SCAN`, default eight), upload completion,
  `POST /api/v1/scans/{id}/analyse`, polling, and
  `GET /api/v1/scans/{id}/result`.

All HTTP failures use a stable JSON error envelope and return an
`X-Correlation-ID` response header. `/api/v1/metrics` is internal-only:
production requires a 32+ character bearer token and the route is omitted from
OpenAPI.

## Expo shell

```bash
pnpm --dir frontend --filter fabricassist-app start
pnpm --dir frontend --filter fabricassist-app web
```

The shell supplies registration, login, camera-first multi-photo capture,
image-library fallback, reordering/removal, processing polling, and localized
rich result screens. Repeated roles are supported; photographed care-label
evidence remains authoritative.
Set `FABRICASSIST_API_PUBLIC_URL` in `.env` for a non-local API host before
building a client.

For local Android development, copy `.env.android.example` to `.env.android`
and run `make start-android`. For a phone connected over trusted Wi-Fi, replace
the Android profile's `localhost` values with the workstation LAN IP and run:

```bash
ANDROID_EXPO_FLAGS=--lan make start-android
```

USB Android development uses `adb reverse`; wireless development uses direct
LAN access and does not use `adb reverse`.

### Enable a real vision LLM

The default `FABRICASSIST_EVIDENCE_PROVIDER=mock` makes no network calls and cannot
recognize a label. To process real photos, add these values to your ignored `.env`
and restart `make up`:

```bash
FABRICASSIST_EVIDENCE_PROVIDER=gemini
FABRICASSIST_CARE_PLANNER_PROVIDER=gemini
FABRICASSIST_CHAT_PROVIDER=gemini
FABRICASSIST_GEMINI_API_KEY=your-secret
FABRICASSIST_GEMINI_MODEL=gemini-2.5-flash
```

Never commit the API key. Provider evidence, proposed plans, and chat claims are
schema validated and every actionable claim passes the deterministic validator.
The Gemini adapter uses the official async Google Gen AI SDK, sends normalized
JPEG bytes directly, requests JSON matching FabricAssist's Pydantic schema, and
then validates both the schema and every source image ID locally.

## Independent model capability interfaces

Application orchestration depends independently on `VisionEvidenceProvider`,
`CarePlanningProvider`, and `ConversationProvider`. The no-network mock, Gemini,
and OpenAI **Responses** adapters are selected by
`FABRICASSIST_EVIDENCE_PROVIDER`, `FABRICASSIST_CARE_PLANNER_PROVIDER`, and
`FABRICASSIST_CHAT_PROVIDER`; neither application services nor care rules contain
SDK, endpoint, header, credential, or provider-selection logic. Each live adapter lives under
`backend/src/fabricassist/infrastructure/vision/providers/`, returns the same
typed contracts, and rejects facts whose source does not match a supplied image.
The composition root converts typed settings into an adapter-specific
configuration whose credential fields are excluded from representations.
Adding another model capability means implementing its port, typed configuration,
factory registration, and shared contract tests without changing application or
domain validation.

Evidence and conversation operations have safe default system prompts. An
adapter may select a reviewed prompt profile tailored to that model while
retaining the same safety constraints, schemas, source validation, prompt
versioning, and deterministic release gate. Provider names and implementation
notes are not sent inside prompt text.

For an OpenAI Responses-compatible gateway (including an Azure API Management
gateway that exposes `/v1/responses`), use the generic configuration below;
gateway-specific headers remain local configuration rather than source code:

```bash
FABRICASSIST_EVIDENCE_PROVIDER=openai_responses
FABRICASSIST_CARE_PLANNER_PROVIDER=openai_responses
FABRICASSIST_CHAT_PROVIDER=openai_responses
FABRICASSIST_OPENAI_RESPONSES_BASE_URL=https://your-gateway.example/openai/v1
FABRICASSIST_OPENAI_RESPONSES_API_KEY=your-local-api-key
FABRICASSIST_OPENAI_RESPONSES_MODEL=your-vision-model-id
FABRICASSIST_OPENAI_RESPONSES_EXTRA_HEADERS_JSON={"X-Gateway-Subscription-Key":"your-local-secret"}
FABRICASSIST_VISION_MAX_INPUT_TOKENS=128000
FABRICASSIST_VISION_MAX_OUTPUT_TOKENS=16000
```

Responses-capable reasoning models can spend output tokens before they emit the
small structured extraction. FabricAssist caps the configured model limits at
`128000` input tokens and `16000` output tokens; keep the corresponding values
at or below those ceilings to avoid gateway rejection or incomplete responses
unrelated to image quality.
`FABRICASSIST_VISION_TIMEOUT_SECONDS` defaults to `120` for the same reason.

### Local vision debugging

For a local debugging session only, set this in the ignored `.env` and restart
the worker:

```bash
FABRICASSIST_VISION_DEBUG_LOGGING=true
docker compose up -d --build fabricassist-worker
docker compose logs -f --tail=100 fabricassist-worker
```

This emits provider/model/operation records with request metadata (text lengths,
image byte counts, MIME types, and schema keys) and response metadata (whether
text was returned, text length, finish reasons, and token counts). Gemini HTTP
failures additionally include the status and a bounded provider diagnostic.
It never logs prompts, response text, image bytes, API keys, gateway headers, or
endpoint URLs. Disable it again after debugging.

## Local infrastructure

`make up` waits for PostgreSQL, Valkey, and MinIO health checks. The one-shot
`fabricassist-minio-init` service creates `FABRICASSIST_S3_BUCKET` and explicitly
sets it private. Local S3 access uses `FABRICASSIST_S3_FORCE_PATH_STYLE=true`.

Run `make smoke` after startup. `make reset-local CONFIRM=1` is destructive only
to the named FabricAssist Compose volumes and refuses non-development/test
environments.

## Local Compose services and ports

The Docker Compose project name is `fabricassist`.

| Service | Local port(s) | Current purpose |
|---|---:|---|
| `fabricassist-postgres` | 5432 | PostgreSQL 17 with pgvector and the Phase 5 baseline schema |
| `fabricassist-valkey` | 6379 | Valkey foundation service |
| `fabricassist-minio` | 9000, 9001 | S3-compatible storage with a private development bucket |
| `fabricassist-api` | 8000 | FastAPI authentication, upload, and scan-result API |
| `fabricassist-worker` | none | Celery worker using Valkey for asynchronous scan processing |

The local PostgreSQL and MinIO values in `.env.example` are intentionally weak
development placeholders. They are not production defaults.

## Observability and production operations

```bash
make observability-up
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```

The optional profile uses local-only Grafana credentials. Production metrics
must be reachable only from an internal scraper and use
`FABRICASSIST_METRICS_ACCESS_TOKEN`. See the
[release](docs/runbooks/release.md), [deployment](docs/runbooks/deployment.md),
and [observability](docs/runbooks/observability.md) runbooks.

The local mock remains deliberately conservative and is not professional
textile-care advice. Production activation still requires named textile-care
validator approval, a licensed/reviewed live provider and product source,
privacy/subprocessor approval, an approved hosted-environment plan, and
successful platform release gates. A separate staging design is deferred.

## Review and privacy lifecycle

Operators use `/api/v1/reviews` to inspect source evidence, proposals, and
validation reports, claim review cases, append a corrected evidence dossier, and
approve the successor result. Corrections never overwrite provider evidence or a
prior proposal. Customers can submit feedback or request review through
`POST /api/v1/scans/{scan_id}/feedback`.

`DELETE /api/v1/scans/{scan_id}` and `DELETE /api/v1/garments/{garment_id}`
create idempotent PostgreSQL deletion requests. Private image objects are put in
a durable outbox and only marked deleted after the storage adapter succeeds;
the API recovery loop retries transient failures automatically for both Celery
and QStash deployments. `FABRICASSIST_DELETION_MAX_ATTEMPTS` bounds retries;
the retention worker task remains available for explicit operational recovery.
Customers can request this deletion from either the garment-history list or a
garment-history detail page after an explicit confirmation. Garment deletion
removes personal analysis, conversation, service-history, and product-lookup
associations while generic product profiles can remain cached.
Short-lived authenticated image previews are available only for retained
images.

Object storage is selected only through `FABRICASSIST_OBJECT_STORAGE_BACKEND`.
The registered `s3` adapter receives redacted `S3ObjectStorageConfig` and
preserves MinIO path-style, AWS workload-identity, and R2 virtual-host
configurations. Product enrichment is independently selected with
`FABRICASSIST_PRODUCT_INFORMATION_PROVIDER`; `mock` is the default and
`http_json` applies HTTPS, host allow-list, DNS/private-address, redirect,
response-size, content-type, and strict-schema checks.

The Expo session provider configures one authenticated generated-client
transport for FabricAssist API operations. It centralizes base URL, access-token
injection, refresh, correlation IDs, and error envelopes. Screens do not call
FabricAssist endpoints with direct `fetch`; presigned binary uploads remain in
the web/native `BinaryUpload` adapter.
