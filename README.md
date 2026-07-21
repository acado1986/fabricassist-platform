# FabricAssist

FabricAssist is a safety-oriented clothing-care assistant for garment owners and
professional cleaning companies. The planned product will analyse garment and
care-label images, validate structured evidence, and use deterministic Python
rules to produce authoritative cleaning guidance.

> **Implementation status — Phase 4 only:** the repository has typed API and
> Expo foundations plus a healthy local dependency stack. It has no
> authentication, uploads, scans, image analysis, model integration, care rules,
> background processing, or customer-facing business functionality.

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

Phase 2 provides `backend/src/fabricassist/` with `fabricassist.api` as the
health-only API package. Phase 3 provides `frontend/apps/client`, the strict
Expo SDK 56 application package `fabricassist-app`, typed `es`/`en` catalogs,
and a generated health-only API client. The worker and all product features
remain deferred.

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
| `make up` | Starts PostgreSQL/pgvector, Valkey, MinIO, private-bucket initialization, and the health-only API. |
| `make down` / `make logs` | Stops or follows the Compose project. |
| `make smoke` | Verifies service health, private bucket access, and API liveness. |
| `make reset-local CONFIRM=1` | Removes only FabricAssist local volumes after an explicit guard. |
| `make test` | Runs foundation checks plus backend and frontend unit tests. |
| `make lint` | Runs configuration validation, Ruff/Pyright, Prettier, ESLint, and TypeScript. |
| `make openapi` | Regenerates `docs/api/openapi.json` and the read-only frontend API client. |
| `make check` | Runs the complete Phase 3 local quality gate. |

`make migrate` and `make seed` intentionally fail with phase-deferred messages:
there is no business schema or seed data in Phase 3.

### Health-only API

After `make up`, the API exposes only:

- `GET http://localhost:8000/api/v1/health/live` — process liveness with no dependency probe.
- `GET http://localhost:8000/api/v1/health/ready` — PostgreSQL connectivity readiness probe.

All HTTP failures use a stable JSON error envelope and return an
`X-Correlation-ID` response header. These endpoints are infrastructure checks,
not product functionality.

## Expo shell

```bash
pnpm --dir frontend --filter fabricassist-app start
pnpm --dir frontend --filter fabricassist-app web
```

The shell supplies an accessible language selector, a not-found route, and a
clearly marked development-only API health diagnostic. It contains no account,
scan, upload, or care-result UI. Set `FABRICASSIST_API_PUBLIC_URL` in `.env` for
a non-local API host before building a client.

## Local infrastructure

`make up` waits for PostgreSQL, Valkey, and MinIO health checks. The one-shot
`fabricassist-minio-init` service creates `FABRICASSIST_S3_BUCKET` and explicitly
sets it private. Local S3 access uses `FABRICASSIST_S3_FORCE_PATH_STYLE=true`.

Run `make smoke` after startup. `make reset-local CONFIRM=1` is destructive only
to the named FabricAssist Compose volumes and refuses non-development/test
environments.

## Local Compose services and ports

The Docker Compose project name is `fabricassist`.

| Service | Local port(s) | Phase 1 status |
|---|---:|---|
| `fabricassist-postgres` | 5432 | PostgreSQL 17 with pgvector image; no business schema |
| `fabricassist-valkey` | 6379 | Valkey foundation service |
| `fabricassist-minio` | 9000, 9001 | S3-compatible storage with a private development bucket |
| `fabricassist-api` | 8000 | Health-only FastAPI foundation; Phase 2 |
| `fabricassist-worker` | none | Inactive Compose placeholder; Phase 8 |

The local PostgreSQL and MinIO values in `.env.example` are intentionally weak
development placeholders. They are not production defaults.

## Phase boundary

Authentication and tenant isolation are deliberately deferred, but must be
implemented before tenant-owned uploads, scan records, review workflows, or
customer history. No LLM, vision provider, OCR, image analysis, deterministic care logic, cache,
AWS deployment, or production secret is part of Phase 4.
