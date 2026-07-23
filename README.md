# FabricAssist

FabricAssist is a safety-oriented clothing-care assistant for garment owners and
professional cleaning companies. The approved target analyses multiple garment,
label, barcode/brand, stain, damage, and construction images; builds sourced
structured evidence; lets AI propose rich care guidance; and releases actionable
claims only after deterministic Python validation. It also remembers physical
garments, service history, sourced product data, and contextual conversations.

> **Implementation status — Phase 17:** authenticated users can collect up to
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

Phase 17 adds tenant-scoped, versioned normalized-image evidence reuse, canonical validated-plan and localized render caches, plus pHash candidate recording. Exact SHA-256 and every schema/prompt/validator/product/template safety field must match before reuse; pHash never authorizes reuse. PostgreSQL stores all cache provenance and counts. Valkey can mirror exact evidence entries when `FABRICASSIST_CACHE_HOT_MIRROR_ENABLED=true`; an outage is a cache miss and cannot remove completed data.

The approved migration is intentionally breaking. When implemented, it removes
the fixed two-photo/narrow v1 API, result, renderer, and `decide_care()` execution
path; old clients and compatibility aliases will not be retained.

## Sources of truth

Read these documents before making changes, in the precedence described by
[`AGENTS.md`](AGENTS.md):

- [Product and technical requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
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
for replacement before using any shared, staging, or production environment.
Never commit `.env` or real credentials.

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
`X-Correlation-ID` response header. These endpoints are infrastructure checks,
not product functionality.

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

### Enable a real vision LLM

The default `FABRICASSIST_VISION_PROVIDER=mock` makes no network calls and cannot
recognize a label. To process real photos, add these values to your ignored `.env`
and restart `make up`:

```bash
FABRICASSIST_VISION_PROVIDER=openai_compatible
FABRICASSIST_VISION_BASE_URL=https://your-provider.example/v1
FABRICASSIST_VISION_API_KEY=your-secret
FABRICASSIST_VISION_MODEL=your-vision-model
```

Use an endpoint compatible with `POST /chat/completions` and image data URLs.
Never commit the API key. In the current legacy slice, the response is
schema-validated and deterministic rules generate the result. The approved
redesign keeps this behavior until Phase 12 replaces it with a typed AI proposal
and deterministic validation gate.

### Azure OpenAI

FabricAssist also supports Azure's deployment-based chat-completions endpoint.
Put these values in ignored `.env`—**do not send the key in chat**—then run
`make up` to recreate the API and worker:

```bash
FABRICASSIST_VISION_PROVIDER=azure_openai
FABRICASSIST_AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
FABRICASSIST_AZURE_OPENAI_API_KEY=your-azure-key
FABRICASSIST_AZURE_OPENAI_DEPLOYMENT=your-vision-deployment-name
FABRICASSIST_AZURE_OPENAI_API_VERSION=2024-10-21
```

The deployment must be vision-capable. FabricAssist sends the image as a base64
data URL to Azure's deployment chat-completions endpoint using the `api-key`
header. This follows the [Azure OpenAI REST reference](https://learn.microsoft.com/en-us/azure/foundry/openai/reference).

## Provider-neutral model interface

The current worker depends only on the `VisionExtractionProvider` interface. Azure OpenAI,
an OpenAI-compatible endpoint, and the no-network mock are infrastructure
adapters selected by `FABRICASSIST_VISION_PROVIDER`; neither the worker nor the
care rules contain vendor-specific logic. Adding another model provider means
implementing and registering one adapter. Planned provider-neutral ports for
evidence extraction, care planning, product information, and conversation are
defined in the architecture and will retain strict schemas and validation gates.

For an OpenAI Responses-compatible gateway, use the generic configuration below;
gateway-specific headers remain local configuration rather than source code:

```bash
FABRICASSIST_VISION_PROVIDER=openai_responses
FABRICASSIST_VISION_BASE_URL=https://your-gateway.example/openai/v1
FABRICASSIST_VISION_API_KEY=your-local-api-key
FABRICASSIST_VISION_MODEL=your-vision-model-id
FABRICASSIST_VISION_EXTRA_HEADERS_JSON={"X-Gateway-Subscription-Key":"your-local-secret"}
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

This emits `vision_model_request` with the prompt, model limits, and normalized
image metadata, plus `vision_model_response` with the model's text output. It
never logs image bytes, API keys, gateway headers, or endpoint URLs. Disable it
again after debugging because model output can include care-label text.

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

## Current limitations

The local mock is intentionally conservative and must not be used as professional
textile-care advice. Contextual chat, cache reuse, human review, complete symbol
coverage, rate limits, external product adapters, and production hardening remain
deferred to the implementation plan.
