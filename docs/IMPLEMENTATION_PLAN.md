# FabricAssist Implementation Plan

**Status:** Proposed implementation sequence; no application code is created by this document.  
**Planning baseline:** 2026-07-20  
**Sources read in full:** `AGENTS.md`, `docs/requirements.md`, and `docs/architecture.md`.

This plan decomposes the MVP into changes that can be implemented, reviewed, and
validated independently. Later phases must not be started merely because an
earlier phase exposes a convenient extension point. Each phase must leave the
repository runnable for the behavior implemented up to that point.

# 1. Project understanding

## Product purpose

FabricAssist is a safety-oriented clothing-care assistant for garment owners and
professional cleaning companies. A user supplies garment and care-label images;
the system extracts visible facts, detects uncertainty, and returns clear,
explainable cleaning instructions in Spanish or English. It is an aid rather
than a guarantee of stain removal, fabric restoration, or a replacement for a
trained textile-care professional.

## Main user journeys

1. **Label-led analysis:** capture or select a label image, pass image-quality
   checks, upload directly to private object storage, start asynchronous
   analysis, and view label facts, prohibitions, recommendations, and confidence.
2. **Garment-only analysis:** capture a garment without a readable label and
   receive explicitly provisional observations plus a request for a label. The
   product must not infer permission to wash, dry clean, or recommend detergent
   from garment appearance alone.
3. **Low-quality or uncertain input:** receive actionable retake guidance for
   blur, glare, crop, folds, darkness, or insufficient resolution; if a better
   image cannot be supplied, request human review.
4. **Safe result reuse:** reuse a validated exact extraction or compatible
   canonical result while retaining origin, validation status, rules versions,
   and reuse count.
5. **Human review:** an operator inspects the original evidence and immutable
   extraction, corrects normalized facts, approves a newly evaluated result, and
   leaves an auditable note.
6. **Account and history:** register or sign in, list and inspect owned scans,
   submit feedback, and request deletion of database associations and stored
   objects.
7. **Tenant administration:** manage operators, retention/language settings,
   active immutable rules versions, audit events, and usage/cost summaries.

## System boundaries

Inside the FabricAssist boundary are:

- A shared Expo application for Android, iOS, authenticated customer web, and
  the initial operator web experience.
- A Python modular monolith built once and run as the independently scalable
  `fabricassist-api` and `fabricassist-worker` processes.
- PostgreSQL, including JSONB and pgvector, as the authoritative business and
  audit store.
- Valkey as transient cache, rate-limit, lock, and Celery coordination
  infrastructure; it is never the sole store of a completed result.
- Private S3-compatible object storage for original and normalized images.
- Repository-owned, versioned care rules, detergent rules, signatures, prompts,
  schemas, and Spanish/English templates.

Outside the core boundary are replaceable vision-model providers, email
delivery, telemetry backends, mobile app stores, CDN/TLS termination, and cloud
resource implementations. They are reached only through ports, standard
protocols, or deployment adapters. FabricAssist does not include payments,
logistics, a custom-trained vision model, a consumer solvent recipe system, or
an autonomous multi-agent decision system in the MVP.

## Role of the Python backend

The backend owns authentication and authorization, tenant-scoped use cases,
presigned upload issuance and verification, scan lifecycle state, asynchronous
job dispatch, image validation and normalization, provider orchestration,
strict schema validation, contradiction detection, deterministic rule
evaluation, result rendering, safe cache selection, reviews, audit, retention,
and deletion. API routes and Celery tasks remain thin; application services
coordinate ports and explicit transactions; infrastructure adapters implement
PostgreSQL, Valkey, S3, Celery, provider, and telemetry details.

## Role of the Expo application

The Expo application provides a shared, accessible customer and operator user
experience on Android, iOS, and web. It owns capture/selection guidance,
platform-specific camera/upload and secure-session adapters, forms and Zod
validation, navigation, polling, localized presentation, and result state. It
does not reproduce backend business rules, trust provisional results as final,
or hand-maintain API interfaces; request and response types are generated from
FastAPI OpenAPI.

## LLM extraction versus deterministic care rules

The model is an evidence extractor. It returns strict structured data covering
image type, original visible label text, normalized symbols/codes, composition,
confidence, unknowns, and provider-run metadata. Pydantic validates syntax,
enums, ranges, cross-field consistency, and explicit unknown states.

Only versioned Python domain rules may turn validated facts into the
authoritative care result. Authority is ordered as explicit written label
instruction, normalized label symbol, material-specific recommendation, then
generic advice. Prohibitions win; contradictions, sensitive materials, and
low-confidence prohibitions cause uncertainty or review. The LLM never decides
whether a cache hit is safe and never supplies authoritative final prose.

## Caching and result-reuse strategy

Caching is evidence-first and versioned:

1. Normalize the image deterministically and look up
   `normalization_version + SHA-256 + extraction_schema_version`.
2. Use perceptual hashes only to discover candidates; never treat proximity as
   proof because one crossed-out symbol can change the safe answer.
3. Build a stable canonical care signature over every safety-relevant fact,
   composition, written warning, schema version, care-rules version, and
   detergent-rules version. Reuse requires exact comparison of relevant fields
   and tenant policy compatibility.
4. Cache rendered answers by canonical result, language, rules/template
   versions, while retaining the durable rendered answer in PostgreSQL.
5. Add pgvector semantic candidate retrieval only after the MVP has sufficient
   human-approved data; semantic similarity can never bypass safety equality.

PostgreSQL stores durable mappings and provenance. Valkey mirrors hot entries
with namespaced/versioned keys and TTLs. Every reuse records source, validation
state, versions, hit count, and invalidation state.

# 2. Assumptions and open decisions

## Assumptions

The following are planning assumptions rather than invented product
requirements. Any assumption that affects behavior must be confirmed or exposed
as configuration before its implementation phase is accepted.

1. The repository is intentionally greenfield; only instruction and design
   documents exist today.
2. `docs/requirements.md`, `docs/architecture.md`, and
   `docs/IMPLEMENTATION_PLAN.md` are the approved source-document locations.
   Root documentation links to these paths without duplicating them.
3. The first release serves one cleaning company operationally, while all
   business records and authorization paths are tenant-scoped from the first
   migration.
4. A scan may contain one or more images classified as `garment`, `label`, or
   `other`; at least one completed upload is required before analysis.
5. The default maximum is 12 MB per image and original-image retention is 30
   days, both overridden by typed environment/tenant settings.
6. Spanish and English are the only activated MVP answer languages. Original
   label text remains unmodified and may be in another language.
7. The deterministic mock provider is the default in development and all
   automated tests. Live-provider tests are explicitly opted in and never run in
   the default quality gate.
8. The initial operator UI remains in the shared Expo web application. A
   separate Next.js portal is deferred until measured UX or deployment needs
   justify it.
9. PostgreSQL stores metadata, normalized facts, audit snapshots, and durable
   cache records, but never image bytes. MinIO/S3 stores images privately.
10. Valkey loss is survivable: queued work may need redispatch and hot cache data
    may disappear, but completed business data remains in PostgreSQL.
11. Direct browser/mobile upload uses presigned single-object operations. The
    server generates object keys and verifies uploaded metadata/content before a
    model call.
12. Development is supported on Linux and macOS with Docker Compose. Android
    native smoke testing also needs the Android SDK/emulator; iOS builds require
    macOS/Xcode and cannot be made Docker-only.
13. Dependency versions are exact in lockfiles and container digests at the time
    their foundation phase is implemented; the version families in section 4
    are deliberate compatibility baselines, not floating production ranges.
14. Customer-visible care-symbol artwork is not needed to complete the initial
    text-and-shape UI; only licensed or original generic illustrations may be
    added later.
15. Normal metadata endpoints use polling for scan progress in the MVP. SSE,
    WebSockets, and push notifications are deferred.
16. UTC is used in persistence and APIs; locale affects rendering, never stored
    canonical facts.
17. Idempotency records are durable in PostgreSQL, with an optional Valkey fast
    path. Valkey alone is insufficient.
18. Phase numbers are delivery gates, not parallel workstreams. A coding agent
    implements only the approved next phase.

## Open decisions

| Decision | Alternatives | Recommendation and reason | Blocks implementation? |
|---|---|---|---|
| Source-document location | Move the source documents to root; keep them in `docs/`; duplicate them | **Resolved: keep `docs/requirements.md`, `docs/architecture.md`, and `docs/IMPLEMENTATION_PLAN.md` in `docs/` and update every reference.** Duplicate sources are prohibited. | No. Resolved before Phase 1 implementation. |
| Python baseline | 3.12, 3.13, or 3.14 | **Python 3.13** pinned to a tested patch. It satisfies 3.12+, remains broadly compatible, and avoids beginning on the 3.12 security-fixes-only branch. Re-evaluate 3.14 after dependency compatibility tests. | No; choose and pin in Phase 2. |
| PostgreSQL baseline | PostgreSQL 17 or 18 | **PostgreSQL 17 + a compatible pgvector release** for a conservative RDS/container baseline; upgrade by normal migration testing when 18 support is confirmed across local and AWS targets. | No; pin in Phase 4. |
| Python type checker | Pyright or mypy | **Pyright**, with strict checks for domain/application modules and documented exceptions at dynamic boundaries. One checker avoids duplicate configuration. | No; decide in Phase 2. |
| SQLAlchemy I/O style | Synchronous sessions; async SQLAlchemy with psycopg 3; mixed sync/async repositories | **Async SQLAlchemy 2 + psycopg 3**, with one session per use case and a controlled async entry point from Celery. This aligns with provider/storage I/O while retaining explicit transactions. Do not create parallel sync and async repository stacks. | No, but must be fixed before Phase 2 implementation. |
| Frontend API generator | `@hey-api/openapi-ts`; Orval; `openapi-typescript` plus hand-written transport | **`@hey-api/openapi-ts`**, generating types and a fetch client into a clearly marked generated package. It avoids manually duplicated request/response interfaces. | No; decide in Phase 3. |
| Commit generated API artifacts | Commit OpenAPI JSON and generated client; regenerate only in builds | **Commit both** and enforce a clean-tree drift check. This makes mobile builds reproducible and reviews show contract changes. Generated files remain read-only. | No. |
| Initial tenant assignment during public registration | Create a tenant per registrant; require invite/tenant code; attach to a configured seeded tenant | **Configured seeded tenant for the single-company MVP**, with operator/admin creation restricted to administrators. Tenant self-service onboarding is deferred. This avoids silently defining a SaaS signup model. | **Blocks the authentication behavior in Phase 6**, not foundations. |
| Administrator/operator management API | Seed-only users; dedicated `/admin/users`; external identity administration | **Small tenant-scoped `/api/v1/admin/users` API** for listing, creating/inviting, and activating operators, because the requirements say administrators manage operators. Exact payloads need API review. | Blocks only the admin portion of Phase 6. |
| JWT signing | HS256 shared secret; EdDSA/RSA key pair; immediate OIDC | **HS256 with a high-entropy rotated secret for the single backend**, short access lifetime, and opaque rotating refresh tokens; keep auth behind ports for later OIDC. An asymmetric key can be adopted before multi-service verification is needed. | No. |
| Refresh-token hash | Plain SHA-256 of high-entropy token; keyed HMAC-SHA-256; password hash | **Keyed HMAC-SHA-256 with a separate server secret**, because refresh tokens are random and need efficient lookup while the key limits damage from a database-only leak. | No; document key rotation before Phase 6. |
| Cross-tenant cache reuse | Global reuse; tenant-only reuse; opt-in shared validated corpus | **Tenant-only by default**, with any cross-tenant human-approved corpus requiring an explicit later policy and privacy review. | No. |
| Care-rule asset format | Python modules; YAML; JSON | **Versioned JSON validated by Pydantic plus focused Python evaluators.** JSON uses the standard parser and yields deterministic serialization; activated content is checksum-locked. | No; decide before Phase 11. |
| Care content authority and symbol artwork | Implement from engineering interpretation; obtain textile-care expert review; license a standard/symbol library | **Require a named textile-care reviewer before activating rules v1; use text/original generic graphics until artwork rights are confirmed.** Engineering tests prove determinism, not domain correctness. | **Blocks activation of Phase 11 rules for production**, but not code structure or tests. |
| Real vision provider/model | Hosted vendor SDK; OpenAI-compatible HTTP endpoint; local compatible server | **OpenAI-compatible HTTP adapter via `httpx`, configured by base URL/model, with the mock as default.** Select a hosted model only after fixture evaluation, privacy, retention, latency, and cost review. | Does not block local MVP implementation; blocks production AI launch. |
| Image normalization details | Preserve broad formats; normalize to JPEG; normalize losslessly | **Decode accepted JPEG/PNG/HEIC where platform support is verified, apply EXIF orientation, strip metadata, bound dimensions/pixels, and create a deterministic sRGB JPEG derivative.** Exact dimensions/quality become `normalization_version=1`. | Threshold/codec details block Phase 7 acceptance, not earlier phases. |
| Perceptual hash implementation | Small maintained library; OpenCV DCT implementation; PostgreSQL extension | **Use a small reviewed image-hash library only if license/maintenance checks pass; otherwise a tested OpenCV DCT implementation.** Candidate status is mandatory either way. | No; Phase 12 decision. |
| Local email | No email capture; Mailpit optional profile; production service immediately | **Mailpit under an optional Compose profile.** Registration can avoid email verification in the single-tenant MVP until an email-verification requirement is approved. | Email verification policy is open but does not block the specified MVP login flow. |
| Infrastructure as code | OpenTofu/Terraform-compatible HCL; AWS CDK; documentation only | **OpenTofu-compatible HCL** under `infrastructure/terraform/`, keeping standard AWS resources and provider-neutral application containers. | No; account/region decisions block only Phase 17 apply. |
| AWS deployment inputs | Fixed project account/region/domain; reusable variables | **Reusable variables with no production identifiers or secrets committed.** Account, region, DNS zone, certificate, budgets, and provider credentials are supplied by deployment environment. | **Blocks actual deployment**, not creation/validation of IaC. |
| Metrics exposure | Public authenticated endpoint; private scrape endpoint; sidecar-only export | **Keep `/api/v1/metrics` disabled or network-restricted in production and expose it to an internal scraper**, while health endpoints remain minimal. | No; decide in Phase 16. |
| Native E2E tool | Maestro; Detox; platform XCTest/Espresso only | **Maestro for the initial Android smoke flow**, retaining Playwright for web. It is smaller than a full Detox setup; reassess if deep native synchronization is required. | No; needed before native feature completion. |

## Detected contradictions and sequencing tensions

1. **Source paths (resolved):** source documents remain at
   `docs/requirements.md`, `docs/architecture.md`, and
   `docs/IMPLEMENTATION_PLAN.md`; root `README.md` and `AGENTS.md` link to them.
2. **Python package path (resolved):** source packages use a `src` layout under
   `backend/src/fabricassist/`. The API and worker entry-point packages are
   `fabricassist.api` and `fabricassist.worker`; domain isolation applies to
   `backend/src/fabricassist/domain/`. ADR-001 records this correction.
3. **Environment-variable names (resolved):** application-owned settings use the
   `FABRICASSIST_` prefix, including `FABRICASSIST_DATABASE_URL` and
   `FABRICASSIST_VISION_PROVIDER`. Narrowly documented standard variables are
   permitted only when a third-party process requires them.
4. **Valkey render-cache example (resolved):** all cache keys use the versioned
   `fabricassist:` namespace; the precise Phase 12 key material remains subject
   to its safety tests and documentation.
5. **Compose process names (resolved):** Compose definitions use canonical
   `fabricassist-<component>` service identifiers, including `fabricassist-api`,
   `fabricassist-worker`, `fabricassist-postgres`, `fabricassist-valkey`, and
   `fabricassist-minio`. Descriptive prose may still say “API” or “worker.”
6. **Requested phase list versus required dependency order:** the prompt lists
   authentication and tenant isolation after review, while the architecture's
   implementation order and ownership requirements put authentication before
   upload. This plan moves authentication to Phase 6 so tenant-owned upload,
   scan, cache, and review behavior is never temporarily implemented without
   authorization.
7. **Phase granularity versus architecture commits:** architecture groups local
   Compose setup into repository foundation and initial tables into backend
   foundation. The prompt asks for independently verifiable infrastructure and
   database phases. This plan splits those commits without changing the selected
   architecture or dependency direction.

# 3. Target repository structure

The tree below is the proposed end-state. Empty directories are not created
merely to match the diagram; each appears in the phase that gives it executable
behavior or documentation. Product source documents remain under `docs/`.

```text
fabricassist-platform/
├── AGENTS.md
├── README.md
├── Makefile
├── .env.example
├── .editorconfig
├── .gitignore
├── .python-version
├── .node-version
├── docker-compose.yml
├── backend/
│   ├── src/
│   │   └── fabricassist/
│   │       ├── __init__.py
│   │       ├── settings.py
│   │       ├── api/
│   │       │   ├── main.py
│   │       │   ├── dependencies/
│   │       │   │   ├── auth.py
│   │       │   │   ├── database.py
│   │       │   │   └── services.py
│   │       │   ├── routes/
│   │       │   │   ├── auth.py
│   │       │   │   ├── health.py
│   │       │   │   ├── scans.py
│   │       │   │   ├── results.py
│   │       │   │   ├── reviews.py
│   │       │   │   ├── admin.py
│   │       │   │   └── metrics.py
│   │       │   ├── errors.py
│   │       │   ├── middleware.py
│   │       │   └── schemas.py
│   │       ├── services/
│   │       │   ├── commands/
│   │       │   ├── queries/
│   │       │   ├── dto/
│   │       │   └── ports/
│   │       │       ├── clock.py
│   │       │       ├── jobs.py
│   │       │       ├── object_storage.py
│   │       │       ├── repositories.py
│   │       │       ├── telemetry.py
│   │       │       └── vision.py
│   │       ├── domain/
│   │       │   ├── auth/
│   │       │   ├── scans/
│   │       │   ├── extraction/
│   │       │   ├── care_rules/
│   │       │   │   └── data/
│   │       │   ├── detergents/
│   │       │   │   └── data/
│   │       │   ├── rendering/
│   │       │   ├── review/
│   │       │   └── shared/
│   │       ├── repositories/
│   │       ├── infrastructure/
│   │       │   ├── database/
│   │       │   │   ├── models/
│   │       │   ├── jobs/
│   │       │   ├── object_storage/
│   │       │   ├── security/
│   │       │   ├── telemetry/
│   │       │   ├── valkey/
│   │       │   └── vision_providers/
│   │       │       ├── mock.py
│   │       │       └── openai_compatible.py
│   │       └── worker/
│   │           ├── celery_app.py
│   │           ├── analyse_scan.py
│   │           ├── delete_scan_assets.py
│   │           └── retention.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── scripts/
│   │   ├── generate_openapi.py
│   │   └── seed.py
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── domain/
│   │   │   └── application/
│   │   ├── integration/
│   │   │   ├── api/
│   │   │   ├── database/
│   │   │   ├── jobs/
│   │   │   ├── object_storage/
│   │   │   └── valkey/
│   │   ├── contract/
│   │   │   ├── providers/
│   │   │   └── openapi/
│   │   ├── migrations/
│   │   └── fixtures/
│   │       ├── images/
│   │       │   ├── clear/
│   │       │   ├── quality_failures/
│   │       │   └── README.md
│   │       ├── extractions/
│   │       └── care_rules/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── apps/
│   │   └── client/
│   │       ├── src/
│   │       │   ├── app/
│   │       │   │   ├── _layout.tsx
│   │       │   │   ├── (auth)/
│   │       │   │   │   ├── login.tsx
│   │       │   │   │   └── register.tsx
│   │       │   │   ├── (customer)/
│   │       │   │   │   ├── scans/
│   │       │   │   │   ├── history/
│   │       │   │   │   └── profile/
│   │       │   │   └── (operator)/
│   │       │   │       └── reviews/
│   │       │   ├── features/
│   │       │   │   ├── auth/
│   │       │   │   ├── capture/
│   │       │   │   ├── scans/
│   │       │   │   ├── results/
│   │       │   │   ├── history/
│   │       │   │   └── reviews/
│   │       │   ├── components/
│   │       │   ├── platform/
│   │       │   │   ├── ImageCapture.native.tsx
│   │       │   │   ├── ImageCapture.web.tsx
│   │       │   │   ├── SecureSession.native.ts
│   │       │   │   ├── SecureSession.web.ts
│   │       │   │   ├── UploadSource.native.ts
│   │       │   │   └── UploadSource.web.ts
│   │       │   ├── config/
│   │       │   └── i18n/
│   │       ├── assets/
│   │       ├── app.config.ts
│   │       ├── package.json
│   │       ├── tsconfig.json
│   │       └── jest.config.js
│   ├── packages/
│   │   ├── api-client/
│   │   │   ├── generated/
│   │   │   └── package.json
│   │   ├── design-tokens/
│   │   ├── translations/
│   │   │   └── src/
│   │   │       ├── en.json
│   │   │       ├── es.json
│   │   │       └── types.ts
│   │   └── test-utils/
│   ├── e2e/
│   │   ├── web/
│   │   └── maestro/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── pnpm-workspace.yaml
│   ├── eslint.config.js
│   ├── prettier.config.js
│   └── Dockerfile
├── infrastructure/
│   ├── compose/
│   │   ├── postgres/
│   │   ├── minio/
│   │   ├── otel/
│   │   └── grafana/
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── network/
│   │   │   ├── data/
│   │   │   ├── object_storage/
│   │   │   ├── compute/
│   │   │   └── observability/
│   │   └── environments/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── production/
│   └── scripts/
│       ├── wait-for-service.sh
│       ├── reset-local.sh
│       └── smoke.sh
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── adr/
│   │   ├── 001-modular-monolith.md
│   │   ├── 002-postgresql-jsonb-pgvector.md
│   │   ├── 003-valkey-coordination.md
│   │   ├── 004-expo-universal-client.md
│   │   ├── 005-deterministic-care-rules.md
│   │   ├── 006-provider-neutral-vision.md
│   │   ├── 007-direct-object-storage-uploads.md
│   │   └── 008-engram-deferred.md
│   ├── api/
│   │   └── openapi.json
│   ├── privacy/
│   │   ├── data-flow.md
│   │   └── retention.md
│   ├── runbooks/
│   │   ├── deployment.md
│   │   ├── rollback.md
│   │   ├── backup-restore.md
│   │   ├── provider-outage.md
│   │   └── deletion-failures.md
│   ├── testing/
│   │   └── fixture-licensing.md
│   └── threat-model.md
└── .github/
    ├── dependabot.yml
    └── workflows/
        ├── backend-quality.yml
        ├── backend-tests.yml
        ├── frontend-quality.yml
        ├── frontend-tests.yml
        ├── contract-drift.yml
        ├── migrations.yml
        ├── containers.yml
        ├── security.yml
        └── deploy.yml
```

# 4. Technology decisions

Exact patch versions must be resolved together, checked for licenses and known
security issues, and committed to `uv.lock`, `pnpm-lock.yaml`, version files, and
container digests. Renovation happens through reviewed pull requests, never by
floating production tags.

## Backend

| Area | Proposed choice | Notes |
|---|---|---|
| Python | **CPython 3.13** | Pin one tested patch in `.python-version` and the backend image. Python 3.12 remains supported by architecture but is already security-fixes-only at this planning date. |
| Package management | **uv** | Project metadata in `pyproject.toml`; reproducible `uv.lock`; no pip requirements split. |
| API | **FastAPI** | REST/JSON `/api/v1`, generated OpenAPI, typed response models, thin handlers. Lock the current compatible stable release in Phase 2. |
| Validation/settings | **Pydantic v2** and **pydantic-settings** | Strict external schemas; typed environment settings using `FABRICASSIST_` prefix. Domain objects remain infrastructure-independent. |
| ORM/database I/O | **SQLAlchemy 2.x async** with **psycopg 3** | Typed declarative mappings, explicit unit-of-work transactions, no ORM imports in domain code. |
| Migrations | **Alembic 1.x** | Every schema change is a new revision; empty/current-schema upgrade and downgrade/rollback intent tested. |
| Database | **PostgreSQL 17** | UUID identifiers, UTC timestamps, CITEXT email, JSONB audit/provider snapshots, typed safety fields and constraints. No MongoDB. |
| Vector support | **pgvector** compatible with the PostgreSQL image | Extension enabled initially so schema compatibility is known; embedding tables and semantic reuse remain post-MVP/optional. |
| Cache/coordination | **Valkey 8.x** using the Redis-compatible protocol | Hot caches, bounded locks, rate limits, Celery broker coordination. Never use Redis-branded services or treat Valkey as authoritative. |
| Task queue | **Celery 5.x** behind a `JobDispatcher` port | Valkey broker initially; database scan state/checkpoints are authoritative. Ignore unnecessary Celery results; RabbitMQ remains a broker-only migration option. |
| Object storage | **S3-compatible port** with a **boto3** adapter | MinIO locally, S3 on AWS, provider-neutral key/metadata/presign semantics in the application port. |
| Image processing | **Pillow** plus **opencv-python-headless** | Decode/bomb limits, EXIF orientation, sRGB normalization, dimensions, blur/brightness/glare, SHA-256, and pHash candidate generation. |
| Provider HTTP | **httpx** | Timeouts, bounded concurrency, request fingerprinting, OpenAI-compatible endpoint, no provider SDK in domain code. |
| Authentication | **argon2-cffi**, **PyJWT**, standard `secrets`/`hmac` | Argon2id passwords, short-lived JWT access tokens, opaque rotating refresh families whose hashes only are stored. |
| Testing | **pytest**, **pytest-asyncio**, **pytest-cov**, **Hypothesis** where invariants help | Unit, API, container integration, migration, provider contract, and table/property-based safety tests. No paid provider in defaults. |
| Formatting/linting | **Ruff formatter and Ruff linter** | One Python style tool, enforced in root Make targets and CI. |
| Type checking | **Pyright** | One static checker; strict in domain/application, explicit/narrow exceptions at third-party boundaries. |
| Telemetry | **OpenTelemetry APIs/SDKs**, Prometheus-compatible metrics, structured JSON logging | Instrumentation stays behind adapters where it touches application use cases. |

## Frontend

| Area | Proposed choice | Notes |
|---|---|---|
| Node.js | **Node.js 24 LTS** | Pin a tested patch. It is the current LTS line at the planning date; production development uses an LTS release only. |
| Package manager | **pnpm 10** workspaces | One lockfile and workspace; Corepack pins the package-manager version. |
| Expo SDK | **Expo SDK 56** | Stable release baseline; use development builds rather than treating Expo Go as production. |
| React Native/React | **React Native 0.85 / React 19.2**, as supplied by Expo SDK 56 | Use `expo install` compatibility resolution; do not independently drift native package versions. |
| TypeScript | **TypeScript 5.x in strict mode** | No `any`; generated API types and typed translation keys. Exact compatible version locked. |
| Navigation | **Expo Router** | Shared route groups for authentication, customer, and operator; platform adapters remain small. |
| Server state | **TanStack Query v5** | Fetch/cache/poll/invalidate API state; do not mirror it into Zustand. |
| Local state | **Zustand v5 only when needed** | Limited to small client-only transient state. Route state, form state, and server state stay in their owning tools. |
| Forms | **React Hook Form v7** | Accessible form state and controlled adapters. |
| Validation | **Zod v4** | Client-side form/environment checks; generated API schemas remain the transport truth. |
| Internationalization | **i18next**, **react-i18next**, **expo-localization** | Typed `es`/`en` catalogs; stable codes map to localized templates; no LLM for routine translations. |
| API client | **`@hey-api/openapi-ts` generated fetch client** | FastAPI OpenAPI is authoritative; generated source is committed and never hand-edited. |
| Camera/files/security | Expo SDK-compatible **expo-camera**, **expo-image-picker**, **expo-file-system**, **expo-secure-store**, plus web adapters | Permissions and browser drag/drop/camera behavior remain platform-isolated. |
| Unit/component tests | **Jest with jest-expo** and **React Native Testing Library** | Test shared behavior and platform adapters with deterministic mocks. |
| End-to-end | **Playwright** for web; **Maestro** Android smoke | iOS smoke is added when a macOS runner is available. |
| Lint/format | **ESLint flat config + eslint-config-expo**, **Prettier** | Lint, formatting check, typecheck, tests, and web build are separate scripts. |
| UI system | React Native primitives, accessibility APIs, and a small shared design-token package | Do not add a broad component framework before product UI needs establish one. |

Official compatibility baselines checked while planning: Expo SDK 56 pairs with
React Native 0.85 and React 19.2; Node 24 is an LTS line. These choices still
require a clean foundation build before they are accepted.

## Infrastructure

| Area | Proposed choice | Notes |
|---|---|---|
| Local orchestration | **Docker Compose v2** with project name `fabricassist` | Health checks, dependency readiness, named volumes, optional profiles, deterministic noninteractive commands. |
| PostgreSQL | Pinned **pgvector PostgreSQL 17** image | Port 5432 locally; health check; test database isolated from development data. |
| Cache/broker | Pinned **Valkey 8.x** image | Port 6379 locally; no externally exposed production endpoint. |
| Object storage | Pinned **MinIO** image plus one-shot `minio-init` | Private bucket, path-style S3 where needed, API 9000 and console 9001 locally. |
| Email | Optional **Mailpit** profile | Local-only capture; UI 8025. |
| Telemetry | Optional **OpenTelemetry Collector** and Grafana/Prometheus-compatible profile | Default development works without the profile. |
| Containers | Multi-stage API/worker image from the same backend source; separate frontend web build image/artifact | Non-root runtime, minimal production stages, SBOM and vulnerability scan. |
| AWS | **ECR, ECS Fargate, ALB, RDS PostgreSQL + pgvector, ElastiCache for Valkey, private S3, CloudFront, Secrets Manager/Parameter Store, CloudWatch/OTEL** | API and worker scale separately; migration runs as a one-off task. |
| AWS IaC | **OpenTofu-compatible HCL** | Reusable modules, remote encrypted state, plan on pull request, approved apply per environment. |
| Provider-neutral alternatives | Generic container host or VM, managed PostgreSQL+pgvector, managed/private Valkey, any private S3-compatible service, OTLP backend | Must support separate API/worker processes, backups, health checks, secrets, rolling deploys, and durable object storage. Kubernetes and a separate vector DB are not MVP dependencies. |

# 5. Delivery phases

The order below deliberately puts authentication before tenant-owned uploads.
It includes all requested phase topics and adds a separate history/deletion phase
so retention work is not hidden inside human review or production hardening.

## Phase 1 — Repository foundation

- **Objective:** Establish the canonical monorepo layout and stable developer
  interface without generating FastAPI or Expo code.
- **Scope:** Apply the resolved `docs/` source-document locations; add root README,
  Makefile targets, safe `.env.example`, ignore/editor/version files, license
  notices, directory ownership notes, ADR templates, CI workflow skeletons, and
  a minimal Compose file that can validate configuration. Record ADR-001 through
  ADR-008 as accepted architecture summaries, not speculative code.
- **Explicitly excluded:** Python/Node dependencies, FastAPI/Expo scaffolding,
  business logic, database tables, deployable cloud resources, live secrets.
- **Files/directories:** Root metadata and commands; `backend/`, `frontend/`,
  `infrastructure/`, `docs/adr/`, `docs/runbooks/`, `.github/workflows/`. Keep
  all three source documents in `docs/` and link to them from root documents.
- **Database changes:** None.
- **API endpoints:** None.
- **Frontend screens/components:** None.
- **Tests:** Shell/config checks for required Make targets, safe environment
  placeholders, canonical naming, and valid Docker Compose/CI YAML.
- **Validation commands:** `make bootstrap`; `docker compose config`; `make lint`;
  `make test`; `make check`; `git diff --check`.
- **Acceptance criteria:** Every required root target exists and is
  noninteractive; commands for implemented scope succeed; README documents
  ports/commands and phased limitations; no secret or application scaffold is
  present; canonical names are consistent.
- **Dependencies:** Approved implementation plan and resolved source-location
  decision.
- **Suggested commit:** `chore(repo): establish FabricAssist repository foundation`

## Phase 2 — Backend foundation

- **Objective:** Create the smallest runnable typed Python service foundation.
- **Scope:** Initialize the `fabricassist` package with FastAPI application
  factory, typed settings, structured JSON logging, correlation middleware,
  stable error envelope, database engine/session wiring, liveness/readiness
  separation, dependency injection composition root, backend Dockerfile, Ruff,
  Pyright, and Pytest configuration.
- **Explicitly excluded:** Business tables/migrations, authentication, scans,
  Celery tasks, object storage, model calls, care rules.
- **Files/directories:** `backend/pyproject.toml`, `backend/uv.lock`,
  `backend/src/fabricassist/{settings.py,api,infrastructure}`, backend
  tests and Dockerfile; root Makefile/Compose entries needed by the API.
- **Database changes:** No business schema; readiness performs a safe connectivity
  probe only.
- **API endpoints:** `GET /api/v1/health/live` and
  `GET /api/v1/health/ready`; stable 404/validation/error envelopes.
- **Frontend screens/components:** None.
- **Tests:** Application startup, settings validation, correlation propagation,
  error envelope, liveness independent of dependencies, readiness success/fail.
- **Validation commands:** `uv sync --frozen`; `uv run ruff format --check backend`;
  `uv run ruff check backend`; `uv run pyright backend`;
  `uv run pytest backend/tests/unit`;
  `docker compose up -d fabricassist-postgres fabricassist-api`;
  `curl --fail http://localhost:8000/api/v1/health/live`.
- **Acceptance criteria:** API container starts without insecure production
  defaults, health semantics are correct, OpenAPI is generated deterministically,
  package imports use `fabricassist.*`, and all backend checks pass.
- **Dependencies:** Phase 1; Python/I/O/type-checker choices.
- **Suggested commit:** `feat(backend): add typed FastAPI service foundation`

## Phase 3 — Frontend foundation

- **Objective:** Create a runnable universal Expo shell with strict TypeScript and
  generated-client plumbing.
- **Scope:** Initialize pnpm workspace and Expo SDK 56 app named
  `fabricassist-app`; configure Expo Router, React Native Web, strict TypeScript,
  responsive/accessibility shell, TanStack Query provider, typed `es`/`en`
  catalogs, environment validation, test setup, development-build metadata, and
  deterministic OpenAPI client generation/drift scripts.
- **Explicitly excluded:** Authentication behavior, camera/upload, server calls
  beyond health smoke, business screens, native store builds.
- **Files/directories:** `frontend/apps/client`, packages for API client,
  translations, design tokens, test utilities; pnpm/ESLint/Prettier/Jest config;
  `docs/api/openapi.json`; root `make openapi` integration.
- **Database changes:** None.
- **API endpoints:** Consume only the existing health contract in a development
  diagnostics test; no new endpoint.
- **Frontend screens/components:** Root layout, language selector, accessible
  shell, not-found screen, and development diagnostics route clearly marked as
  non-product behavior.
- **Tests:** Catalog key parity/type safety, app config/product naming, root
  render, responsive navigation shell, API generator drift fixture.
- **Validation commands:** `pnpm --dir frontend install --frozen-lockfile`;
  `pnpm --dir frontend format:check`; `pnpm --dir frontend lint`;
  `pnpm --dir frontend typecheck`; `pnpm --dir frontend test`;
  `pnpm --dir frontend build:web`; `make openapi`; `git diff --exit-code`;
  Docker frontend build target.
- **Acceptance criteria:** Web shell runs, Android/iOS configuration uses
  FabricAssist names, TypeScript is strict, user-visible shell text is catalogued,
  generated sources are reproducible/read-only, and no auth/scan placeholder is
  presented as working.
- **Dependencies:** Phases 1–2; generated-client choice.
- **Suggested commit:** `feat(frontend): create universal Expo foundation`

## Phase 4 — Local infrastructure

- **Objective:** Provide a deterministic healthy local dependency stack for all
  later integration phases.
- **Scope:** Pin PostgreSQL+pgvector, Valkey, MinIO, and `minio-init`; add named
  networks/volumes, health checks, private development bucket initialization,
  path-style configuration, API readiness dependencies, optional Mailpit and
  OTEL profiles, reset/inspection scripts, and test-specific isolated services.
- **Explicitly excluded:** Celery worker behavior, production credentials,
  business migrations, cloud resources, real provider.
- **Files/directories:** `docker-compose.yml`, `infrastructure/compose/**`,
  `infrastructure/scripts/{wait-for-service.sh,reset-local.sh,smoke.sh}`,
  `.env.example`, README, Make targets.
- **Database changes:** Enable extensions required by the approved schema
  baseline (`vector`, `citext`) through migrations in Phase 5, not ad hoc init SQL.
- **API endpoints:** Existing readiness endpoint must reflect PostgreSQL and
  required dependency state without leaking connection details.
- **Frontend screens/components:** None.
- **Tests:** Compose config, all dependency health checks, bucket private by
  default, path-style upload smoke, Valkey ping, PostgreSQL connection, clean
  reset/recreate.
- **Validation commands:** `make up`; `docker compose ps`;
  `docker compose exec fabricassist-postgres pg_isready`;
  `docker compose exec fabricassist-valkey valkey-cli ping`;
  MinIO health/API and bucket-policy checks; `make down`; local reset smoke.
- **Acceptance criteria:** Fresh `.env` from `.env.example` starts without paid
  services; healthy services use documented ports; no public bucket; reset only
  affects the named local project after explicit confirmation/target invocation.
- **Dependencies:** Phases 1–2; PostgreSQL/Valkey image choices.
- **Suggested commit:** `chore(infra): add healthy local dependency stack`

## Phase 5 — Database schema and migrations

- **Objective:** Establish migration discipline and the tenant/auth/scan storage
  needed by the next vertical slices.
- **Scope:** Configure Alembic; create extensions and initial `tenants`, `users`,
  `refresh_sessions`, `scans`, `scan_images`, `idempotency_records`, and
  `ruleset_versions` tables; use UUIDs, tenant FKs, UTC timestamps, constrained
  string enums/checks, indexes, optimistic scan version, and seed one development
  tenant/admin without production credentials.
- **Explicitly excluded:** Authentication endpoints, image bytes, provider and
  extraction tables, care results, reviews, embeddings, production seed data.
- **Files/directories:** SQLAlchemy models/repositories, Alembic config and first
  revisions, `backend/scripts/seed.py`, migration/repository tests, schema docs.
- **Database changes:** New extensions/tables/indexes/checks above; downgrade
  intentionally removes only this baseline on an empty/test database.
- **API endpoints:** None beyond health.
- **Frontend screens/components:** None.
- **Tests:** Empty-database upgrade, downgrade/upgrade round trip, migration from
  previous revision, tenant FK/index constraints, UTC/UUID behavior, repository
  transaction rollback, seed idempotency.
- **Validation commands:** `make up`; `make migrate`; `make seed`;
  `uv run alembic -c backend/alembic.ini current`;
  migration test suite against Compose PostgreSQL; `make check`.
- **Acceptance criteria:** A fresh and previous supported database migrates to
  head; schema matches models without drift; all tenant-owned baseline tables
  contain `tenant_id`; no images/secrets/raw tokens are stored.
- **Dependencies:** Phases 2 and 4; tenant bootstrap decision.
- **Suggested commit:** `feat(database): add tenant and scan schema baseline`

## Phase 6 — Authentication and tenant isolation

- **Objective:** Deliver secure sign-in/session lifecycle and enforce ownership
  before tenant-owned features exist.
- **Scope:** Register/login/refresh/logout; Argon2id password policy; short-lived
  access JWT; opaque rotating refresh-token families with hash-only persistence,
  revocation and reuse detection; web HttpOnly cookie plus CSRF/origin defense;
  native SecureStore adapter; role/tenant authorization dependencies; configured
  MVP tenant assignment; minimal admin operator management if approved.
- **Explicitly excluded:** OIDC, email verification unless separately approved,
  social login, scan behavior, unrestricted cross-tenant administration.
- **Files/directories:** Auth domain/application/infrastructure/API modules,
  auth migrations if baseline needs expansion, frontend auth feature/routes and
  platform secure-session files, threat-model/session docs.
- **Database changes:** Password hashes and refresh-session token/family hashes,
  revocation/reuse timestamps, safe device metadata, indexes; optional audit
  records for security events if audit table is introduced here.
- **API endpoints:** `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout`;
  tentatively tenant-admin `GET/POST/PATCH /api/v1/admin/users` if approved.
- **Frontend screens/components:** Register/login forms, session bootstrap,
  logout, role-aware route protection, web/native token adapters, localized
  validation/error states.
- **Tests:** Argon2 parameters, generic login failures, rotation and replay-family
  revocation, cookie flags/CSRF, native secure-store mock, disabled users, roles,
  cross-user/tenant denial, rate-limit contract.
- **Validation commands:** Backend auth unit/integration tests against Compose;
  frontend lint/type/test/web build; Playwright registration/login/logout flow;
  `make openapi`; `make check`; manual Android development-build login smoke.
- **Acceptance criteria:** Raw passwords/refresh tokens never persist or log;
  replay revokes the family; web/native storage follows requirements; every
  protected test resource rejects wrong user/tenant/role; OpenAPI/client match.
- **Dependencies:** Phases 3 and 5; tenant assignment/admin decisions.
- **Suggested commit:** `feat(auth): add rotating tenant-scoped sessions`

## Phase 7 — Image upload workflow

- **Objective:** Create tenant-owned scans and safely upload private images
  directly to S3-compatible storage.
- **Scope:** Storage port and MinIO/S3 adapter; server-generated object keys;
  idempotent scan creation; short-lived presigned upload constraints; upload
  completion verification; MIME/declared/actual size, decoded format, dimension,
  pixel/bomb checks; original retention metadata; mobile camera/library and web
  file/drag-drop/camera adapters; crop/rotate/retake controls.
- **Explicitly excluded:** Analysis dispatch, LLM calls, final normalization/hash,
  care results, public image URLs.
- **Files/directories:** Scan/upload application/API/storage modules; image
  validation utilities; capture/upload frontend feature and platform files;
  MinIO contract tests; upload security docs.
- **Database changes:** Complete `scan_images` metadata/object-key lifecycle and
  any upload-attempt/idempotency fields; scan transitions `draft` → `uploading`;
  retention timestamps. No blob columns.
- **API endpoints:** `POST /api/v1/scans` and
  `POST /api/v1/scans/{scan_id}/uploads/complete`; protected
  `GET /api/v1/scans/{scan_id}` for upload state.
- **Frontend screens/components:** Start scan, label/garment capture guidance,
  native picker/camera, web drag-drop/file/browser-camera, preview/crop/rotate,
  upload progress/retry, rejection guidance.
- **Tests:** Object-key injection resistance, URL expiry/scope, MIME/size mismatch,
  malformed/bomb/oversize images, unauthorized completion, duplicate idempotency,
  private bucket, platform adapter component tests, synthetic licensed fixtures.
- **Validation commands:** Unit/integration/storage contract suites with MinIO;
  `make openapi`; frontend checks; Docker web upload smoke; manual Android camera
  smoke; `make check`.
- **Acceptance criteria:** A signed-in user uploads an allowed image without API
  byte proxying; another user/tenant cannot read or complete it; invalid content
  is rejected before model use; no full presigned URL/object key leaks in logs or
  normal responses beyond the required upload instruction.
- **Dependencies:** Phases 4–6; normalization/codec threshold decision.
- **Suggested commit:** `feat(scans): add private presigned upload workflow`

## Phase 8 — Asynchronous scan processing

- **Objective:** Add a retryable, idempotent analysis skeleton with authoritative
  database state.
- **Scope:** `JobDispatcher` port, Celery/Valkey adapter and worker process,
  `POST analyse`, persisted operation key/checkpoints, short bounded lock plus
  database state verification, stages for validation/normalization/quality/hash,
  progress polling, bounded retry categories, crash recovery, and failed-job
  visibility. Use a deterministic internal placeholder result only as an
  explicitly incomplete test stage; do not claim analysis completion yet.
- **Explicitly excluded:** Provider interface/output, real extraction, care
  decision, caching/review, unbounded task chains.
- **Files/directories:** Jobs port/adapter, Celery app, `analyse_scan` orchestration,
  worker Docker/Compose service, scan status domain/service/routes, frontend
  polling/status feature, worker tests/runbook.
- **Database changes:** Job operation/checkpoint table or scan checkpoint fields,
  attempts/lease timestamps/error category; controlled transitions through
  `queued`, `processing`, `needs_better_image`, `failed` (not `completed`).
- **API endpoints:** `POST /api/v1/scans/{scan_id}/analyse` returning 202 and
  idempotent operation state; enhanced `GET /api/v1/scans/{scan_id}`.
- **Frontend screens/components:** Processing/progress screen, polling backoff,
  recoverable failure and retake guidance states.
- **Tests:** Duplicate dispatch, worker retry categories/backoff bounds, invalid
  state no-retry, lock expiry/crash recovery, Valkey loss/redispatch behavior,
  quality thresholds, no paid call, tenant ownership, polling cleanup.
- **Validation commands:** Start full Compose API/worker stack; worker unit and
  Valkey integration tests; kill/restart worker smoke; submit same idempotency key
  twice; frontend status tests; `make check`.
- **Acceptance criteria:** API never holds the model workflow request open; one
  logical scan operation is safe under duplicate delivery; a worker crash cannot
  leave a permanent lock; unusable images stop before provider stage; business
  state is recoverable from PostgreSQL.
- **Dependencies:** Phase 7.
- **Suggested commit:** `feat(worker): add idempotent scan processing skeleton`

## Phase 9 — LLM provider abstraction and mock provider

- **Objective:** Define a provider-neutral vision boundary and make all local and
  automated analysis deterministic.
- **Scope:** `VisionExtractionProvider` protocol, normalized image/context DTOs,
  categorized failures, provider registry selected by typed configuration,
  deterministic fixture-backed mock provider, invocation timeout/concurrency
  interfaces, prompt/schema version placeholders that are explicit metadata.
- **Explicitly excluded:** Final extraction schema breadth, real network provider,
  model prose as result, care rules, paid calls.
- **Files/directories:** Application vision port, infrastructure mock adapter and
  registry, mock fixture schema/data, provider contract test suite, configuration
  and provider docs.
- **Database changes:** Introduce `model_runs` with provider/model/operation,
  prompt/schema versions, request fingerprint, latency, nullable token/cost,
  status/error category and tenant/scan IDs. Do not store private request bodies.
- **API endpoints:** No new public endpoint; scan status may expose safe provider
  stage/error code, not payload or model internals.
- **Frontend screens/components:** No new screen; existing processing states map
  stable error codes to localized guidance.
- **Tests:** One shared provider contract for mock and future adapters; exact
  deterministic fixtures; timeout/transient/permanent/schema failure mapping;
  secret/payload log redaction; configured provider selection.
- **Validation commands:** Provider contract/unit tests; worker integration with
  mock and no network access; Docker repeated scan smoke; `make check`.
- **Acceptance criteria:** Default local startup processes fixtures without any
  API key/network provider; worker depends only on the port; every invocation has
  auditable safe metadata; failure categories drive retry policy.
- **Dependencies:** Phase 8.
- **Suggested commit:** `feat(vision): add provider port and deterministic mock`

## Phase 10 — Structured label extraction

- **Objective:** Validate complete, language-independent label facts before they
  can reach care rules.
- **Scope:** Strict Pydantic extraction boundary and internal domain types for all
  required care categories, original visible text, confidence and explicit
  unknowns; numeric/enum/cross-field/composition validation; contradiction and
  confidence policy; versioned prompt/schema assets; OpenAI-compatible `httpx`
  adapter with mocked HTTP contract tests; persist immutable original and
  validated payloads.
- **Explicitly excluded:** Final care decision/prose, automatic repair loops beyond
  one configured constrained retry, live-provider requirement, semantic cache.
- **Files/directories:** Extraction domain schemas/validators, prompt/schema
  assets, provider HTTP adapter, extraction repositories, versioned AI fixtures,
  evaluation command/docs.
- **Database changes:** `label_extractions`, `extracted_materials`, and
  `extracted_care_facts`; typed/indexed safety fields plus JSONB immutable provider
  and validated snapshots; supersession/human-correction markers; explicit
  `tenant_id` on every tenant-owned table even when a parent FK also implies it.
- **API endpoints:** No new endpoint; safe scan detail may expose normalized facts
  only after authorization, never raw provider payload.
- **Frontend screens/components:** Retake/uncertainty state using stable codes;
  optional detected-facts development/operator component, not final result UI.
- **Tests:** Spanish/English/mixed text preservation, missing/unknown symbols,
  invalid enums/ranges, percentages, contradictions, garment-only restrictions,
  sensitive materials, schema retry limit, synthetic HTTP responses, fixture
  evaluation with no paid API.
- **Validation commands:** Extraction unit/property/contract/fixture suites;
  worker integration with mock; opt-in live test command verified as skipped by
  default; migration checks; `make check`.
- **Acceptance criteria:** Invalid output never reaches rules; absent evidence is
  `unknown`, never inferred; original text is preserved; garment-only extraction
  cannot authorize care; low confidence produces retake/review candidates;
  provider metadata is complete where available.
- **Dependencies:** Phase 9; production provider selection remains deferred.
- **Suggested commit:** `feat(extraction): validate structured care-label facts`

## Phase 11 — Deterministic care-rules engine

- **Objective:** Produce the authoritative canonical care and detergent decision
  from validated facts only.
- **Scope:** Explicit enums/value objects, immutable care-rules v1 and separate
  detergent-rules v1 assets, checksum registration/activation guard, precedence,
  prohibitions, material fallbacks, professional-only wording codes,
  contradiction/sensitive-case review outcomes, canonical structured result,
  no-wash/no-detergent safety invariant.
- **Explicitly excluded:** Localized prose/templates, caching, model-generated
  explanation, admin rule editor, unreviewed production activation.
- **Files/directories:** `domain/care_rules`, `domain/detergents`, versioned data,
  services and exhaustive unit/regression fixtures; ADR-005 detail/rule-change
  documentation.
- **Database changes:** `care_results` with source extraction, normalized JSONB
  snapshot plus selected typed safety fields, care/detergent rule versions,
  validation status; immutable `ruleset_versions` checksums/activation state.
- **API endpoints:** `GET /api/v1/scans/{scan_id}/result` returns a structured
  canonical result/status; no customer prose yet.
- **Frontend screens/components:** Typed internal result-state fixtures only;
  customer rendering arrives in Phase 13.
- **Tests:** Table-driven every rule branch; explicit all prohibited/contradictory
  combinations; label-over-material precedence; garment-only denial; sensitive
  leather/suede/fur review; detergent categories/softener/bleach; immutable
  activated checksum; deterministic output snapshot.
- **Validation commands:** Domain unit/property/regression tests without Docker;
  repository integration and migrations with PostgreSQL; worker end-to-end mock
  extraction to canonical result; `make check`.
- **Acceptance criteria:** Same input+versions always produces the same object;
  every completed result references active immutable versions; prohibitions win;
  no domestic detergent when water washing is prohibited; contradictions and
  configured sensitive cases never become confidently completed results.
- **Dependencies:** Phase 10; care expert approval blocks production activation.
- **Suggested commit:** `feat(care): add versioned deterministic care rules`

## Phase 12 — Exact and canonical result caching

- **Objective:** Safely avoid repeat provider/rule work without weakening care
  constraints.
- **Scope:** Versioned normalization derivative; SHA-256 exact mappings; pHash
  candidate discovery with mandatory verification; stable canonical
  serialization/signature hash; tenant-scoped validated-result lookup;
  PostgreSQL durable records and Valkey hot mirrors; reuse count/provenance and
  invalidation; provider-call spy proving exact reuse.
- **Explicitly excluded:** Semantic/pgvector reuse, cross-tenant reuse, fuzzy
  automatic truth, rendering cache (Phase 13).
- **Files/directories:** Image fingerprint/cache application/domain adapters,
  canonical serializer, Valkey namespaced key definitions, cache docs and tests.
- **Database changes:** `image_fingerprints` and durable cache provenance fields/
  indexes on extraction/results; canonical hash uniqueness scoped by tenant
  policy and versions; invalidation reason/hit count/origin; explicit `tenant_id`
  on every tenant-owned cache/fingerprint record.
- **API endpoints:** No new endpoint; authorized result metadata may include safe
  `reuse_source` and validation state.
- **Frontend screens/components:** Small result provenance label if UX-approved;
  no cache decisions in frontend.
- **Tests:** Normalization/hash stability, one-pixel/crossed-symbol pHash candidate
  non-reuse, schema/rules mismatch miss, prohibition/temperature/process mismatch
  miss, invalidated/human states, tenant isolation, Valkey loss fallback,
  concurrent hit count, repeated exact input makes zero additional provider calls.
- **Validation commands:** Unit/property tests; PostgreSQL+Valkey integration;
  full Compose same-image twice and assert model-run count; cache-key snapshot;
  `make check`.
- **Acceptance criteria:** Exact validated compatible input avoids provider call;
  canonical equivalent reuses only exact safety facts/versions; Valkey flush does
  not lose durable cache; all keys use documented `fabricassist:` namespace;
  unsafe pHash candidates never auto-reuse.
- **Dependencies:** Phase 11; cross-tenant and pHash decisions.
- **Suggested commit:** `feat(cache): add safe exact and canonical result reuse`

## Phase 13 — Multilingual result rendering

- **Objective:** Render authoritative canonical results accessibly in Spanish and
  English without another LLM call.
- **Scope:** Typed rendering codes and parameterized templates, prohibitions-first
  sections, distinction among detected/interpreted/recommended/prohibited/
  professional-only/uncertain facts, template version/checksum, durable rendered
  answers and Valkey mirror, language selection/fallback, accessible shared result
  screen.
- **Explicitly excluded:** Additional languages, unvalidated generative prose,
  visual reproduction of protected care symbols, separate web portal.
- **Files/directories:** Backend rendering domain/assets/service, frontend typed
  catalogs/result feature, translation tests, cache-key/version docs.
- **Database changes:** `rendered_answers` unique by care result/language/template
  version within its tenant, explicit `tenant_id`, rendering ruleset registration,
  and render provenance/hit count as needed.
- **API endpoints:** Localized `GET /api/v1/scans/{scan_id}/result?language=es|en`
  while retaining canonical structured codes in the response contract.
- **Frontend screens/components:** Result screen, prohibition/warning summary,
  detected-vs-recommended sections, professional-only/uncertainty banners,
  accessible language switch and loading/error states.
- **Tests:** Catalog parity, typed key/parameter coverage, temperatures and
  prohibitions unchanged by rendering, ES/EN snapshots, language fallback,
  screen reader labels, no color-only meaning, dynamic text, render cache version
  misses, Valkey fallback.
- **Validation commands:** Backend render tests and integration; frontend unit/
  component/accessibility checks; Playwright result flow in both languages; web
  build; Android screen smoke; `make openapi`; `make check`.
- **Acceptance criteria:** Same canonical result renders correct ES/EN templates;
  no LLM call is made; numeric/safety facts exactly match canonical data; cached
  output includes language/template/rule versions; provisional state is explicit.
- **Dependencies:** Phases 11–12.
- **Suggested commit:** `feat(results): render typed Spanish and English guidance`

## Phase 14 — Human-review workflow

- **Objective:** Allow authorized operators to correct uncertain evidence and
  approve a newly evaluated auditable result.
- **Scope:** Review triggers for low confidence, contradictions, sensitive
  materials and user request; cursor-paginated queue/detail; assignment/status;
  edits create a superseding human-corrected extraction while preserving the
  original; rules rerun; approval activates result and may validate tenant cache;
  customer-facing note; feedback types and audit events.
- **Explicitly excluded:** Feedback directly mutating results, in-place provider
  payload edits, automatic rule authoring, cross-tenant operators, unlicensed
  image sharing.
- **Files/directories:** Review domain/application/API/repositories, audit adapter,
  frontend operator review routes/components and customer feedback controls,
  review docs/tests.
- **Database changes:** `review_cases`, `feedback`, `audit_events`, assignment/
  resolution indexes, superseding extraction relationships, human-approved result
  status. Every tenant-owned row contains `tenant_id`.
- **API endpoints:** `GET /api/v1/reviews`,
  `GET/PATCH /api/v1/reviews/{review_id}`,
  `POST /api/v1/reviews/{review_id}/approve`, and
  `POST /api/v1/scans/{scan_id}/feedback` with idempotency where required.
- **Frontend screens/components:** Operator queue/detail, confidence/evidence
  editor, correction confirmation, approval/note, customer review status and
  feedback/request-review controls.
- **Tests:** Role/tenant isolation, cursor pagination, optimistic concurrent edit,
  immutable original, correction validation, rules rerun, approval idempotency,
  audit redaction/before-after summary, cache provenance, feedback cannot mutate,
  accessible operator web components.
- **Validation commands:** Backend unit/integration/security tests; frontend
  component tests; Playwright customer-request → operator-correct → customer-view
  flow; migration/OpenAPI drift; `make check`.
- **Acceptance criteria:** Required cases enter review; only same-tenant operators
  can inspect/correct; original evidence remains auditable; approval uses Python
  rules and records actor/time/versions; customer sees the approved result.
- **Dependencies:** Phases 6 and 13.
- **Suggested commit:** `feat(review): add auditable operator correction flow`

## Phase 15 — Scan history, deletion, and retention

- **Objective:** Complete customer lifecycle and privacy-preserving removal of
  scans and stored images.
- **Scope:** Cursor-paginated owned history/detail; preview URLs only when retained;
  idempotent delete request; database tombstone/personal-association policy;
  auditable retryable object deletion worker; retention scheduler; failed deletion
  visibility/retry; documented derived-metric policy.
- **Explicitly excluded:** Immediate unsafe hard deletion across transactions,
  retaining images beyond policy, billing/logistics, undelete unless approved.
- **Files/directories:** History/deletion/retention services/routes/tasks,
  frontend history/detail/delete confirmation/profile settings, retention and
  deletion runbooks/tests.
- **Database changes:** Deletion requests/state/attempts or outbox records,
  tombstone/deleted timestamps, retention indexes and safe audit references;
  ensure object references are cleared only after successful deletion policy.
- **API endpoints:** `GET /api/v1/scans`, detailed
  `GET /api/v1/scans/{scan_id}`, and `DELETE /api/v1/scans/{scan_id}`.
- **Frontend screens/components:** History list/detail, retained-image preview,
  deletion confirmation/progress/failure, empty state, feedback/review state.
- **Tests:** Cursor ordering, ownership/tenant denial, short-lived preview scope,
  duplicate delete, MinIO transient retry, worker crash, retention boundary/time,
  no orphaned objects after success, audit without sensitive paths, legal-policy
  fixtures.
- **Validation commands:** PostgreSQL/MinIO/Celery integration; advance test clock;
  full Compose upload→complete→delete and inspect bucket/DB; Playwright history/
  delete; Android smoke; `make check`.
- **Acceptance criteria:** Users see only owned scans; deletion is traceable and
  eventually removes objects/personal associations; failures are retryable and
  visible; retention runs do not delete active/in-policy images.
- **Dependencies:** Phase 14 and worker/storage foundations.
- **Suggested commit:** `feat(history): add auditable scan deletion and retention`

## Phase 16 — Observability, security, and privacy

- **Objective:** Apply cross-cutting production controls and demonstrate safe
  operation without changing domain authority.
- **Scope:** End-to-end correlation IDs/traces; structured redacted logs; required
  API/queue/job/model/cache/review/storage/DB metrics; internal metrics exposure;
  rate limits for auth/scan/upload/analysis; explicit CORS; secure headers/TLS
  assumptions; global/per-tenant model concurrency; secret validation; upload and
  decompression limits; privacy data-flow/threat model; audit coverage; optional
  local OTEL profile.
- **Explicitly excluded:** AWS resources, vendor-specific telemetry in domain,
  public metrics, secrets in repository, unsupported compliance certification.
- **Files/directories:** Telemetry/security/Valkey adapters and middleware,
  Compose OTEL profile, `docs/threat-model.md`, privacy docs/runbooks, security and
  observability tests.
- **Database changes:** Only migration-backed indexes/audit/security metadata
  proven necessary; no log/image payload storage.
- **API endpoints:** Harden liveness/readiness; `GET /api/v1/metrics` internal-only
  or disabled in production by policy; admin usage diagnostics may expose
  tenant-aggregated safe metrics through an authorized endpoint if specified.
- **Frontend screens/components:** Privacy/retention disclosure, safe global error
  states, optional authorized admin usage summary; no raw telemetry UI.
- **Tests:** Rate limits, CORS allowlist, cookies/headers, log snapshot redaction,
  presigned URL masking, correlation across API/job/provider, concurrency caps,
  dependency outage readiness, tenant metric isolation, security regression
  suite and fixture privacy/license manifest.
- **Validation commands:** Full Compose OTEL smoke; `make check`; dependency and
  secret scanners; load bursts for rate/concurrency limits; inspect logs/traces;
  web accessibility/security headers check.
- **Acceptance criteria:** Required metrics/traces/logs exist with no forbidden
  data; production rejects insecure defaults; rate/concurrency controls work;
  health endpoints disclose no sensitive details; privacy/retention/provider
  subprocessors are documented.
- **Dependencies:** Phases 6–15 so the complete flow can be instrumented.
- **Suggested commit:** `feat(platform): add security and observability controls`

## Phase 17 — AWS deployment

- **Objective:** Describe and provision a reviewable AWS staging topology while
  keeping application protocols portable.
- **Scope:** OpenTofu modules for network/private subnets/security groups, ECR,
  ECS API/worker, ALB, RDS PostgreSQL+pgvector, ElastiCache Valkey, private S3 with
  lifecycle, CloudFront web, secrets references, logs/metrics, backups, autoscale,
  one-off migration task, budgets/tags; build/deploy/rollback runbooks and staging
  CI plan/apply gates.
- **Explicitly excluded:** Hard-coded account IDs/secrets/domains, automatic
  production apply, Kubernetes, multi-region, a mandatory paid AI provider, EAS
  dependency, database migration inside API startup.
- **Files/directories:** `infrastructure/terraform/modules/**` and environment
  compositions, deployment/rollback/backup runbooks, deploy workflow definitions,
  environment-variable mapping documentation.
- **Database changes:** No application schema beyond tested current migrations;
  enable extensions and run Alembic as controlled one-off deployment action.
- **API endpoints:** No new business endpoint; ALB uses liveness/readiness with
  appropriate public/private exposure.
- **Frontend screens/components:** No new product UI; publish Expo web artifact
  behind CloudFront; document native environment configuration.
- **Tests:** `tofu fmt/validate`, lint/security policy checks, plan in disposable
  or approved staging account, container architecture/start smoke, migration job,
  private network/bucket assertions, backup configuration, rollback rehearsal.
- **Validation commands:** Local `tofu fmt -check -recursive` and `tofu validate`;
  container builds/SBOM/scans; mocked/static IaC tests; approved staging `plan`;
  post-deploy smoke. No `apply` is required to validate the implementation PR.
- **Acceptance criteria:** Plan contains no secret/production identifier;
  API/worker scale separately; data services are private/encrypted/backed up;
  images are private/lifecycle-managed; migration and rollback steps are explicit;
  same containers still run through local Compose/provider-neutral hosts.
- **Dependencies:** Phase 16; AWS account/region/domain inputs only for apply.
- **Suggested commit:** `feat(deploy): add portable AWS staging baseline`

## Phase 18 — Production hardening

- **Objective:** Prove the complete MVP meets safety, reliability, performance,
  release, and recovery criteria before production launch.
- **Scope:** Full regression/evaluation gate for selected model; p95/cache/load
  tests; retry/dead-letter operational drills; database backup/restore drill;
  object deletion/provider outage/Valkey loss exercises; dependency/container
  scanning and update policy; OpenAPI/migration drift gates; Android release and
  smoke; iOS CI/release when macOS runner is available; accessibility review;
  runbooks/alerts/SLOs; rules/domain and privacy approval records.
- **Explicitly excluded:** Optional pgvector semantic reuse, new languages,
  payments, logistics, multi-region, custom-model training, autonomous agents.
- **Files/directories:** CI hardening, load/security/evaluation tests, release
  profiles, dashboards/alerts/runbooks, fixture/version manifests, production
  readiness checklist.
- **Database changes:** Only measured index/tuning migrations using
  expand/migrate/contract; no history rewrites. Verify backup/restore and previous
  image compatibility.
- **API endpoints:** No required new endpoints; freeze and validate the MVP
  OpenAPI contract and documented error codes.
- **Frontend screens/components:** Fix only release/accessibility/platform gaps;
  no new feature scope. Complete Android smoke and iOS when runner exists.
- **Tests:** Entire section 6 strategy, load/security/accessibility, failure
  injection, rules/provider fixture evaluation, upgrade/rollback, backup restore,
  Android native critical flow, web E2E.
- **Validation commands:** `make check`; full clean `make up`/migrate/seed/smoke;
  CI matrix; container build/SBOM/vulnerability scan; approved load test;
  Alembic previous→head and restore drill; Playwright/Maestro; opt-in selected
  provider evaluation with synthetic/licensed fixtures only.
- **Acceptance criteria:** All 13 MVP acceptance criteria in requirements are
  demonstrated; documented p95 targets meet expected MVP load or an approved risk
  states evidence/mitigation; no high/critical unresolved vulnerability; restore,
  rollback, provider outage, Valkey loss and worker crash procedures are proven;
  domain/privacy/licensing approvals are recorded.
- **Dependencies:** Phases 1–17 and production provider/domain approvals.
- **Suggested commit:** `chore(release): complete FabricAssist production readiness`

# 6. Testing strategy

All default suites are deterministic and use synthetic or appropriately licensed
fixtures. Network access to paid providers is denied or unconfigured by default.

## Unit tests

- Domain enums/value objects, scan state transitions, permissions, idempotency
  decisions, signature serialization, translation parameters, and review logic.
- Application services use in-memory/fake ports and explicit clocks/UUID sources;
  infrastructure behavior belongs in integration/contract suites.
- Use table-driven tests for finite safety branches and Hypothesis selectively
  for invariants such as “prohibition cannot produce allowed advice.”

## Integration tests

- Run API, repositories, jobs, locks/rate limits, and storage contracts against
  real PostgreSQL+pgvector, Valkey, MinIO, and Celery services under Docker
  Compose. Do not substitute SQLite, filesystem blobs, or an in-memory Redis
  clone for default integration claims.
- Each suite creates isolated tenant/data prefixes and removes them without
  touching developer data.

## API contract tests

- Assert status codes, response models, stable string enums, ISO-8601 UTC dates,
  cursor pagination, error envelope/correlation ID, idempotency, and auth cookies.
- Generate `docs/api/openapi.json` and the frontend client, then fail on Git
  drift. Never hand-edit generated sources.
- Exercise backward-compatible examples and provider/internal data redaction.

## Database and migration tests

- Upgrade from empty to head, previous supported revision to head, and intended
  downgrade/upgrade round trips.
- Compare model metadata to migration head; test extensions, indexes, FK/check/
  unique constraints, UUIDs, UTC, optimistic locking, tenant columns, and seed
  idempotency.
- Use real PostgreSQL, not SQLite. Add expand/migrate/contract tests when a
  rolling rollback must remain possible.

## Worker tests

- Unit-test orchestration stages and retry classification with fake ports.
- Integrate duplicate delivery, expired locks, persisted checkpoints, worker
  termination/restart, bounded backoff, Valkey outage/redispatch, provider timeout,
  schema failure, storage failure, and final database state.
- Assert deterministic failures do not blind-retry and exhausted jobs become
  operator-visible `failed` states.

## Frontend component tests

- React Native Testing Library covers auth forms, capture guidance, upload and
  polling states, prohibition-first result sections, provisional/uncertain
  banners, history, review editing, deletion, and platform adapter contracts.
- Test accessible labels, focus/keyboard behavior for web, dynamic text, screen
  reader order, and meaning independent of color.
- Mock generated API transport, not hand-written response types.

## End-to-end tests

- Playwright web critical path: register/login → create scan → direct MinIO upload
  → analyze with mock → poll → result ES/EN → exact reuse → request review →
  operator correction/approval → history → deletion.
- Cross-tenant negative flows run with separate browser contexts.
- Maestro provides at least an Android development-build smoke for auth, camera/
  selection, upload, processing, result, and logout. iOS CI is added on an
  available macOS runner.

## LLM fixture-based tests

- Version fixtures for clear/incomplete labels; blur/glare/folds/crop/low
  resolution; Spanish/English/mixed/original other-language text; written
  supplements; contradictions; dry-clean-only/do-not-dry-clean; wool/silk/
  technical/leather/suede/fur; unknown symbols/fields; garment-only/unrelated.
- Expected data asserts normalized facts, unknowns, confidence ranges, and review
  outcome, not brittle provider prose.
- The mock returns these fixtures exactly. The OpenAI-compatible adapter uses an
  in-process synthetic HTTP server/transport. Live evaluation is opt-in and
  cannot gate ordinary pull requests unless separately funded/approved.

## Care-rule regression tests

- One case for every rule and detergent branch, every label/material precedence,
  all prohibited combinations, professional-only handling, sensitive category,
  unknown, and contradiction.
- Activated fixture outputs and checksums are immutable. A new version adds new
  fixtures rather than overwriting old expected history.
- Verify rendering cannot alter permissions or numeric temperatures.

## Image test fixtures

- Programmatically create simple safe fixtures where possible; repository images
  must have a source/license manifest and contain no real customer data.
- Include dimensions/size/format/EXIF/metadata, malformed and decompression-bomb
  simulations that are safe for CI, quality signals, normalization SHA, pHash
  candidate behavior, and garment-vs-label classification fixtures.
- Never copy protected official symbol artwork without confirmed rights.

## Cache-reuse tests

- Prove exact compatible repeat causes no additional provider invocation.
- Prove schema, normalization, rules, detergent, template, language, invalidation,
  tenant, prohibition, temperature, process-letter, and warning mismatches miss.
- Prove pHash/semantic candidates cannot become hits without exact safety field
  comparison; Valkey flush falls back to PostgreSQL; concurrent hits update
  provenance safely.

## Security and tenant-isolation tests

- For every tenant-owned API/repository, create user A/tenant A, user B/tenant A,
  and user C/tenant B and assert role plus ownership behavior.
- Cover registration/login rate limits, enumeration resistance, Argon2id, refresh
  rotation/replay, CSRF/cookie/CORS, idempotency ownership, object key/URL scope,
  upload MIME/size/decode/bomb defense, log/audit redaction, preview expiry,
  operator/admin restrictions, and eventually consistent deletion.
- Run dependency, secret, IaC, SBOM, and container vulnerability scanning in CI.

# 7. Local development workflow

The exact commands below are the intended stable workflow once their owning
phase exists. A phase must update README/Make targets when it makes a command
real; documentation must never claim an unimplemented target is functional.

## Initial setup

```bash
git clone <repository-url> fabricassist-platform
cd fabricassist-platform
cp .env.example .env
make bootstrap
make up
make migrate
make seed
make check
```

`make bootstrap` verifies/pins Docker Compose, uv, Node/Corepack/pnpm, and platform
prerequisites and installs locked local dependencies noninteractively. It must not
fetch a model or require a paid account.

## Environment variables

- `.env.example` contains safe local placeholders only; `.env` is ignored.
- Application-owned variables use `FABRICASSIST_`, including:
  `FABRICASSIST_ENVIRONMENT`, URLs/CORS, PostgreSQL, Valkey/Celery, object storage,
  provider/model/timeout/concurrency, JWT/refresh hash keys, retention/upload
  limits, OTEL, and log level under that prefix.
- `FABRICASSIST_VISION_PROVIDER=mock` is the local/default test value.
- Production settings reject local credentials, wildcard CORS, absent signing
  keys, and insecure storage/provider settings at startup.

## Starting and stopping Docker services

```bash
make up
docker compose ps
make logs
make down
```

`make up` starts PostgreSQL, Valkey, MinIO/init, `fabricassist-api`, and—once
Phase 8 exists—`fabricassist-worker`. Optional services use explicit profiles,
for example
`docker compose --profile mail --profile observability up -d`.

## Starting the API outside Docker

Keep dependency services running, then:

```bash
uv run --project backend uvicorn fabricassist.api.main:app --reload --host 0.0.0.0 --port 8000
```

Use `FABRICASSIST_DATABASE_URL` and related `.env` settings pointing to Compose.
The supported default remains `docker compose up fabricassist-api` so container
parity is always testable.

## Starting the worker outside Docker

After Phase 8:

```bash
uv run --project backend celery --app fabricassist.worker.celery_app:app worker --loglevel=INFO
```

Do not use a production queue/database from a developer `.env`.

## Starting Expo

```bash
pnpm --dir frontend --filter fabricassist-app start
pnpm --dir frontend --filter fabricassist-app android
pnpm --dir frontend --filter fabricassist-app ios   # macOS/Xcode only
pnpm --dir frontend --filter fabricassist-app web
```

Normal native development uses an Expo development build. Android emulators must
reach the documented host API alias; physical devices use an explicit LAN URL
allowed by development CORS. Never bake localhost or secrets into a production
bundle.

## Migrations and seed data

```bash
make migrate
make seed
uv run --project backend alembic -c backend/alembic.ini current
```

Create revisions through the documented Alembic command, inspect them manually,
and test empty plus previous-schema upgrades. API/worker startup never creates or
migrates production schema automatically.

## Tests and quality gates

```bash
make test
make lint
make openapi
make check
```

Backend-focused commands:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest backend/tests
```

Frontend-focused commands:

```bash
pnpm --dir frontend format:check
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build:web
```

Integration/E2E commands start isolated Docker dependencies through Make/Compose.
No default command contacts a paid provider.

## Resetting local data

```bash
make down
make reset-local   # explicit local-only guard; removes FabricAssist named volumes
make up
make migrate
make seed
```

`reset-local` must verify the Compose project name/environment and print the
volumes it will remove. It must refuse production-like environments and must not
be a hidden part of `make down`.

## Inspecting local services

```bash
# MinIO console
open http://localhost:9001

# Valkey (never print secrets or full cached private content)
docker compose exec fabricassist-valkey valkey-cli PING
docker compose exec fabricassist-valkey valkey-cli --scan --pattern 'fabricassist:*'

# PostgreSQL
docker compose exec fabricassist-postgres psql -U fabricassist -d fabricassist

# API health
curl --fail http://localhost:8000/api/v1/health/live
curl --fail http://localhost:8000/api/v1/health/ready
```

MinIO local credentials are safe development placeholders documented in README;
production credentials and complete presigned URLs must never be printed or
committed.

# 8. CI/CD plan

Pull-request CI uses pinned actions, least-privilege permissions, concurrency
cancellation, dependency caches keyed by lockfiles, and no fork access to
secrets. Default jobs use the mock provider.

## CI jobs

1. **Backend formatting and linting:** checkout, install uv, `uv sync --frozen`,
   `ruff format --check backend`, `ruff check backend`.
2. **Backend type checking:** same lockfile environment, `pyright backend`; upload
   only safe diagnostics.
3. **Backend tests:** fast unit job plus Docker-service integration matrix for
   PostgreSQL+pgvector, Valkey, MinIO, and worker; coverage and fixture evaluation;
   live provider excluded.
4. **Frontend formatting and linting:** pin Node/Corepack/pnpm, frozen install,
   Prettier check and ESLint.
5. **Frontend TypeScript:** strict typecheck, typed translation/catalog checks,
   generated sources included.
6. **Frontend tests:** Jest/RNTL and web build; Playwright critical flow with the
   Compose mock stack. Android emulator smoke runs on protected/main/nightly CI;
   iOS when a macOS runner is approved.
7. **OpenAPI contract drift:** generate OpenAPI and API client from backend,
   compare clean Git tree, run contract examples.
8. **Migration validation:** fresh upgrade, previous supported revision upgrade,
   schema/model drift, intentional downgrade/upgrade, extension availability.
9. **Docker image builds:** multi-platform where required, API and worker from the
   shared backend, frontend web artifact; run image health smoke, generate SBOM,
   do not push on untrusted pull requests.
10. **Dependency and security scanning:** Python/JavaScript dependency audit,
    secret scan, SAST where useful, container/IaC scan, license policy, fixture
    privacy/license manifest. High/critical exceptions need owner/expiry.

`make check` remains the local equivalent of required non-platform CI. CI can
split it for speed but must not use different rules.

## Deployment stages

1. **Pull request:** quality, tests, contract/migration drift, IaC validation,
   container build without push, security scan.
2. **Main integration:** sign and push immutable image digests to ECR; publish
   internal web/native artifacts; deploy automatically only to a disposable or
   approved development environment using the mock provider where practical.
3. **Staging:** protected approval; OpenTofu plan review; migration one-off task;
   deploy API then worker with rolling health gates; web artifact to CloudFront;
   synthetic smoke, provider fixture evaluation, deletion/rollback checks.
4. **Production:** separate human approval, selected exact digests, backup check,
   migration expand/migrate/contract gate, rolling deploy/canary if available,
   post-deploy smoke and metrics review. Never auto-promote solely on main merge.
5. **Rollback:** restore previous API/worker/web digests; only roll database back
   when the reviewed migration explicitly supports it. Prefer forward fixes and
   backward-compatible expansion. Document object/rule/template compatibility.

# 9. Risks and mitigations

| Risk | Mitigation and verification |
|---|---|
| Incorrect care-symbol interpretation | Preserve original evidence; strict codes/confidence/unknowns; contradiction checks; textile expert review of rules/fixtures; sensitive/prohibition cases route to review; never claim engineering tests prove textile correctness. |
| LLM hallucinations | Model extracts only; strict schema/range/cross-field validation; missing evidence is `unknown`; at most one constrained schema retry; deterministic rules own decisions; fixture evaluation and provider promotion gate. |
| Incompatible cached result reuse | Version normalization/schema/rules/detergent/templates/keys; tenant scope; exact safety-field comparison; pHash/vector are candidates only; invalidation/provenance; regression cases for a single crossed-out symbol and temperature/process mismatches. |
| Blurred or incomplete labels | Pre-provider quality signals and thresholds; actionable retake guidance; stop unusable input before paid call; uncertainty/review fallback; quality fixture set with configurable tested thresholds. |
| Personal data in uploaded images | Private buckets/URLs, EXIF stripping on normalized derivatives, no image/request logging, short retention/default 30 days, deletion workflow, provider retention/privacy review, tenant isolation, least privilege, encryption and documented data flow. |
| High image-storage cost | Configurable retention/lifecycle expiry, normalized derivatives sized for inference, no DB blobs, deletion retry, bucket metrics/budgets, avoid duplicate originals where privacy policy allows only through references—not unsafe shared access. |
| Long-running AI requests | Async jobs, client polling, hard provider timeout, global/per-tenant concurrency, persisted stages, bounded retries/backoff/jitter, p95 metrics, no long HTTP request, cancellation/failed visibility. |
| Provider outages | Provider-neutral port, mock/local compatibility, categorized retry, circuit/concurrency controls, queue backpressure, operator retry action, cached validated results where safe, outage runbook, no fabricated fallback answer. |
| Mobile/web camera differences | Small `.native`/`.web` adapters, shared business/UI states, file-library fallback, platform permissions, device/emulator/browser matrix, clear guidance, no scattered `Platform.OS`. |
| Trademark/licensing restrictions for care-symbol artwork | Use text/original generic shapes until rights are confirmed; record fixture/artwork provenance and license; do not copy protected official symbol sets; legal/domain approval gate before branded artwork. |
| Tenant data leakage | `tenant_id` in every business table, tenant criteria inside repositories, role/ownership tests for every route, private object prefixes and scoped presigns, tenant-scoped cache default, audit and metric isolation. |
| Unsafe rule change | Immutable activated versions/checksums, new version rather than mutation, exhaustive regression fixtures, domain expert approval, result/signature/version provenance, rollback-compatible activation. |
| Valkey loss or duplicate Celery delivery | PostgreSQL state/checkpoints authoritative; idempotency keys and constraints; short expiring lock only as optimization; redispatch/recovery tests; durable results/cache mappings in PostgreSQL. |
| Deletion partial failure | Transactional request/outbox state, idempotent object deletion task, retry/visibility/audit, tombstone and association policy, retention reconciliation job and runbook. |
| Dependency/version drift | Lockfiles and pinned images/actions, generated-client drift, Renovate/Dependabot review, SBOM/vulnerability/license scans, Expo compatibility checks and upgrade smoke. |
| PostgreSQL/provider/cloud lock-in | Standard SQL/JSON/S3/HTTP/OTLP/container boundaries, AWS only in adapters/IaC, pgvector inside authoritative DB but optional for MVP, export/backup/restore drills. |
| Cost or latency abuse | Authentication/scan/upload/analysis rate limits, file limits, idempotency, concurrency quotas, model/token/cost metrics, budgets and admin summaries. |

# 10. Definition of done

## Global definition of done

FabricAssist MVP is done only when:

1. The complete customer and operator flows satisfy the 13 MVP acceptance
   criteria in the requirements locally with Docker Compose and in staging.
2. Model output is strict structured evidence only; deterministic versioned
   Python rules are the sole authority for care and detergent decisions.
3. Prohibitions, contradictions, garment-only cases, low confidence, and
   sensitive materials fail safely and have exhaustive regression coverage.
4. PostgreSQL is authoritative; Valkey loss cannot erase completed data; images
   remain private in S3-compatible storage and are removed by the retention/
   deletion workflow.
5. Authentication, rotating refresh sessions, role/tenant/ownership enforcement,
   rate limits, CORS, secrets, log redaction, and audit/privacy controls pass
   negative tests.
6. Spanish and English accessible web/mobile results are rendered from typed
   templates without changing canonical facts.
7. Exact and canonical safe reuse avoids repeat provider work and records all
   provenance/versions; unsafe candidate mismatches demonstrably miss.
8. FastAPI OpenAPI and the generated TypeScript client have no drift.
9. Every schema change has an Alembic migration tested from empty and previous
   supported schema; production rollout/rollback compatibility is documented.
10. `make bootstrap`, `up`, `down`, `logs`, `migrate`, `seed`, `test`, `lint`,
    `openapi`, and `check` are real, deterministic, documented commands.
11. Ruff, Pyright, Pytest, ESLint/Prettier, TypeScript, frontend tests/web build,
    E2E, migrations, images, and security scans pass; no command is claimed if it
    was not run.
12. API/worker containers scale separately and deploy through documented,
    recoverable stages; backup/restore, provider outage, Valkey loss, worker crash,
    deletion retry, and rollback drills are recorded.
13. No secrets, customer images, private URLs, protected symbol artwork, or paid
    provider dependency exist in the repository/default CI.
14. Documentation, `.env.example`, ADRs, runbooks, OpenAPI, migrations, and
    generated client are synchronized with behavior.
15. Remaining limitations are explicitly deferred rather than represented as
    complete.

## Phase-level checklist

Each phase is done only when all boxes applicable to that phase are checked:

- [ ] Scope and exclusions match the approved phase; no later phase began.
- [ ] Architecture dependency directions and canonical naming are preserved.
- [ ] New behavior has unit plus appropriate integration/contract/UI tests.
- [ ] Tenant/ownership/security/privacy negative cases are covered where data is
      tenant-owned or external.
- [ ] Database changes have a new Alembic revision, constraints/indexes,
      empty/previous-schema tests, and intentional downgrade behavior.
- [ ] API changes use response models/error envelope and regenerate OpenAPI/client
      with zero drift.
- [ ] Frontend changes keep TypeScript strict, copy in catalogs, shared behavior,
      accessibility, and platform adapters.
- [ ] Docker-local smoke proves the phase; native-specific behavior also has the
      required device/emulator check.
- [ ] Formatting, linting, type checking, tests, and relevant build commands were
      actually run successfully.
- [ ] README/configuration/environment/security/retention/rule/cache/provider
      documentation changed with behavior.
- [ ] No secrets, private customer data, unsafe logs, unlicensed fixtures, or
      floating dependencies were introduced.
- [ ] Acceptance criteria are demonstrated and the completion report lists files,
      commands/results, migration/env instructions, and remaining risks.
- [ ] The commit is focused, buildable, and uses the suggested imperative format.

# 11. Recommended first implementation task

After this plan and the source-document-location decision are approved, Codex
should implement **Phase 1 — Repository foundation only**.

The exact task is:

> Establish the canonical FabricAssist monorepo directories and root developer
> interface; resolve the requirements/architecture file location without
> duplicating sources; add README, safe `.env.example`, Makefile targets,
> editor/ignore/version metadata, ADR records/templates, Compose configuration
> validation, and CI skeletons. Add configuration/naming checks and run every
> Phase 1 validation command. Do not initialize Python dependencies, generate a
> FastAPI project, initialize pnpm/Expo, create migrations, or begin later phases.

That is the smallest coherent first delivery because it resolves the current
source-path contradiction, fixes canonical conventions before generated files
exist, creates the stable command surface all later phases depend on, and can be
reviewed without conflating framework or product behavior.
