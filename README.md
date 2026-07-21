# FabricAssist

FabricAssist is a safety-oriented clothing-care assistant for garment owners and
professional cleaning companies. The planned product will analyse garment and
care-label images, validate structured evidence, and use deterministic Python
rules to produce authoritative cleaning guidance.

> **Implementation status — local analysis slice:** authenticated users can capture
> or upload either a care-label or garment image, optionally add the other for
> context, queue the scan for asynchronous processing, and view a localized result.
> The default deterministic mock intentionally returns a review-safe outcome. A
> real, OpenAI-compatible vision LLM is opt-in through uncommitted environment
> variables. The LLM extracts facts only; deterministic Python rules produce the
> safety-critical care answer.

## Sources of truth

Read these documents before making changes, in the precedence described by
[`AGENTS.md`](AGENTS.md):

- [Product and technical requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

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
- authenticated scan creation with either image upload (and an optional second
  image), upload completion, `POST /api/v1/scans/{id}/analyse`, polling, and
  `GET /api/v1/scans/{id}/result`.

All HTTP failures use a stable JSON error envelope and return an
`X-Correlation-ID` response header. These endpoints are infrastructure checks,
not product functionality.

## Expo shell

```bash
pnpm --dir frontend --filter fabricassist-app start
pnpm --dir frontend --filter fabricassist-app web
```

The shell supplies registration, login, camera-first image capture, image-library
upload, processing polling, and localized result screens. The care-label field is
shown first because it provides the most detailed evidence, but either field can
start a scan.
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
Never commit the API key. The LLM response is schema-validated; the final answer
is rendered from the validated facts and deterministic safety rules.

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

The worker depends only on the `VisionExtractionProvider` interface. Azure OpenAI,
an OpenAI-compatible endpoint, and the no-network mock are infrastructure
adapters selected by `FABRICASSIST_VISION_PROVIDER`; neither the worker nor the
care rules contain vendor-specific logic. Adding another model provider means
implementing and registering one adapter, while retaining the same strict
structured extraction schema and deterministic final-care rules.

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

The v1 extraction schema and care rules are intentionally narrow and must not be
used as professional textile-care advice. Caching, human review workflows,
complete symbol coverage, rate limits, and production hardening remain deferred.
