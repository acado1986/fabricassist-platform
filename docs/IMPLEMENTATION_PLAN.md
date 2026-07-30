# FabricAssist Implementation Plan

**Status:** Living implementation sequence for the existing local analysis slice.
**Planning baseline:** 2026-07-20; garment-intelligence redesign approved 2026-07-22.
**Sources read in full:** `AGENTS.md`, `docs/requirements.md`, and `docs/architecture.md`.

This plan decomposes the MVP into changes that can be implemented, reviewed, and
validated independently. Later phases must not be started merely because an
earlier phase exposes a convenient extension point. Each phase must leave the
repository runnable for the behavior implemented up to that point.

# 1. Project understanding

## Product purpose

FabricAssist is a safety-oriented clothing-care assistant for garment owners and
professional cleaning companies. A user supplies multiple garment, label,
barcode/brand, stain, damage, and construction images. The system builds a
source-referenced evidence dossier, retrieves trusted product information when
available, lets AI propose a rich care plan, validates every actionable claim,
and returns explainable guidance in Spanish or English. It remembers physical
garments, evidence revisions, conversations, and confirmed service history while
remaining an aid rather than a guarantee of stain removal or a replacement for
a trained textile-care professional.

## Main user journeys

1. **Multi-photo analysis:** capture one to eight images with repeatable roles,
   pass per-image quality checks, upload directly to private object storage,
   extract source-referenced evidence, validate an AI-proposed plan, and view a
   rich result with sources, prohibitions, recommendations, and confidence.
2. **Garment-only analysis:** capture a garment without a readable label and
   receive explicitly provisional observations plus a request for a label. The
   product must not infer permission to wash, dry clean, or recommend detergent
   from garment appearance alone.
3. **Low-quality or uncertain input:** receive actionable retake guidance for
   blur, glare, crop, folds, darkness, or insufficient resolution; if a better
   image cannot be supplied, request human review.
4. **Remembered garment:** recognize an exact physical garment or ask the user to
   confirm a probable/product/visual candidate, reuse stable verified evidence,
   inspect only new images where safe, and revalidate the complete merged plan.
5. **Product enrichment:** decode and validate supported barcodes, query trusted
   adapters, show source/match/retrieval state, and keep the physical label above
   catalog care information.
6. **Contextual conversation:** answer follow-ups from the active garment dossier,
   plan, service history, rolling summary, prior messages, and relevant images;
   validate actionable claims before delivery.
7. **Safe result reuse:** reuse a validated exact extraction or compatible
   canonical result while retaining origin, validation status, rules versions,
   and reuse count.
8. **Human review:** an operator inspects the original evidence and immutable
   extraction, corrects normalized facts, approves a newly evaluated result, and
   leaves an auditable note.
9. **Account and history:** register or sign in, list and inspect owned garments,
   analyses, conversations, and service events,
   submit feedback, and request deletion of database associations and stored
   objects.
10. **Tenant administration:** manage operators, retention/language settings,
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
- Repository-owned, versioned evidence/proposal/chat schemas, validation policies,
  signatures, prompts, context summaries, barcode normalization, and
  Spanish/English templates.

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
strict schema validation, contradiction detection, garment identity resolution,
incremental evidence merging, barcode/product lookup, AI planning, deterministic
validation, result rendering, contextual conversation, safe cache selection,
reviews, audit, retention, and deletion. API routes and Celery tasks remain thin; application services
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

## AI proposals versus deterministic validation

The evidence model returns strict source-referenced facts. A planning model may
then return a strict `ProposedCarePlan`, and a conversation model may return
typed actionable claims. Pydantic validates syntax, enums, ranges, cross-field
consistency, evidence references, and explicit unknown states.

Versioned Python validators accept, warn, block, request another image, or
require review. They never silently invent a replacement plan. One constrained
retry may consume machine-readable violations. Photographed written/symbol care
instructions remain above exact manufacturer data, verified catalog data,
material recommendations, and generic advice. Prohibitions win; free-form prose
is never the sole authoritative output.

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

Garment memory is not a cache. PostgreSQL separately stores physical garments,
product profiles, instance/product identifiers, immutable/superseding evidence
revisions, conversations, and append-only service events. A retail barcode or
visual match remains a confirmation candidate; only a verified instance
identifier or previously confirmed relationship auto-links.

# 2. Assumptions and open decisions

## Assumptions

The following are planning assumptions rather than invented product
requirements. Any assumption that affects behavior must be confirmed or exposed
as configuration before its implementation phase is accepted.

1. The repository already contains a runnable local authentication, upload,
   asynchronous analysis, provider, narrow extraction, deterministic care, and
   Expo result slice. New phases migrate it without rewriting applied migrations
   or historical results.
2. `docs/requirements.md`, `docs/architecture.md`, and
   `docs/IMPLEMENTATION_PLAN.md` are the approved source-document locations.
   Root documentation links to these paths without duplicating them.
3. The first release serves one cleaning company operationally, while all
   business records and authorization paths are tenant-scoped from the first
   migration.
4. A scan may contain one to eight completed images by default, using repeatable
   `garment_overview`, `care_label`, `composition_label`,
   `barcode_brand_label`, `stain_closeup`, `damage_closeup`,
   `construction_detail`, or `other` roles.
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
19. Product-information coverage is optional and incomplete by design; the mock
   returns deterministic exact/ambiguous/not-found fixtures without network access.
20. Conversation state is authoritative in PostgreSQL; provider conversation
   identifiers are optional adapter metadata.

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
| Validation-policy asset format | Python modules; YAML; JSON | **Versioned JSON validated by Pydantic plus focused Python validators.** JSON uses the standard parser and deterministic serialization; activated content is checksum-locked. | No; decide before the care-validation phase. |
| Care content authority and symbol artwork | Unvalidated AI prose; validator-gated structured AI plan; deterministic plan generator | **Resolved by ADR-009: typed AI proposal plus deterministic accept/warn/block/review validation. Require a named textile-care reviewer before activating validator v1; use text/original generic graphics until artwork rights are confirmed.** | **Blocks production validator activation**, not code structure or tests. |
| Maximum images per scan | Two; eight; provider maximum | **Eight completed images by default, configurable, with repeated roles.** Provider adapters may batch or reject above their safe capability, but the domain/API do not assume two. | No; implement in Phase 10. |
| Physical garment identity | Barcode; visual match; user confirmation; FabricAssist tag | **Only a verified FabricAssist/instance identifier or prior confirmed relationship auto-links.** Barcode/product/visual composites remain candidates requiring confirmation. | No; resolved by ADR-010. |
| Product-information provider | Commercial catalog; manufacturer adapters; generic web search; mock only | **Provider-neutral port with deterministic mock first.** Select real sources after licensing, coverage, privacy, and contract evaluation; arbitrary web/QR fetching is not a fallback. | Real source blocks production enrichment, not local behavior. |
| Conversation transport | Synchronous request; queued REST; SSE/WebSocket | **Persisted asynchronous message status first**, compatible with later SSE streaming. PostgreSQL context remains authoritative regardless of transport. | No; streaming is deferred. |
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
   `FABRICASSIST_EVIDENCE_PROVIDER`,
   `FABRICASSIST_CARE_PLANNER_PROVIDER`,
   `FABRICASSIST_CHAT_PROVIDER`,
   `FABRICASSIST_OBJECT_STORAGE_BACKEND`, and
   `FABRICASSIST_PRODUCT_INFORMATION_PROVIDER`. Narrowly documented standard variables are
   permitted only when a third-party process requires them.
4. **Valkey render-cache example (resolved):** all cache keys use the versioned
   `fabricassist:` namespace; the precise Phase 17 key material remains subject
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
8. **Original care authority (resolved):** ADR-005 and the original deterministic
   plan generator are superseded by ADR-009. The redesign is a breaking cutover:
   remove the old image/result/care execution path instead of preserving aliases,
   compatibility mappers, dual writes, or fallback behavior.
9. **Barcode identity ambiguity (resolved):** a barcode may identify a product
   variant but not one physical garment. ADR-010 separates `product_profile`
   from `garment`; only exact instance identifiers auto-link.

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
│   │       │   │   ├── garments.py
│   │       │   │   ├── conversations.py
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
│   │       │       ├── vision.py
│   │       │       ├── care_planning.py
│   │       │       ├── conversations.py
│   │       │       └── product_information.py
│   │       ├── domain/
│   │       │   ├── auth/
│   │       │   ├── scans/
│   │       │   ├── extraction/
│   │       │   ├── care/
│   │       │   │   ├── evidence/
│   │       │   │   ├── proposal/
│   │       │   │   └── validation/
│   │       │   ├── detergents/
│   │       │   │   └── validation/
│   │       │   ├── garments/
│   │       │   ├── products/
│   │       │   ├── conversations/
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
│   │       │   ├── product_information/
│   │       │   └── vision_providers/
│   │       │       ├── mock.py
│   │       │       └── openai_compatible.py
│   │       └── worker/
│   │           ├── celery_app.py
│   │           ├── analyse_scan.py
│   │           ├── answer_message.py
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
│   │       ├── proposals/
│   │       ├── validation/
│   │       ├── products/
│   │       ├── identity/
│   │       └── conversations/
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
│   │       │   │   │   ├── garments/
│   │       │   │   │   ├── conversations/
│   │       │   │   │   ├── history/
│   │       │   │   │   └── profile/
│   │       │   │   └── (operator)/
│   │       │   │       └── reviews/
│   │       │   ├── features/
│   │       │   │   ├── auth/
│   │       │   │   ├── capture/
│   │       │   │   ├── scans/
│   │       │   │   ├── results/
│   │       │   │   ├── garments/
│   │       │   │   ├── product-information/
│   │       │   │   ├── conversations/
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
│   │   ├── 008-engram-deferred.md
│   │   ├── 009-validator-gated-ai-care-plans.md
│   │   ├── 010-durable-garment-identity-and-history.md
│   │   ├── 011-trusted-product-information-lookup.md
│   │   └── 012-server-owned-contextual-conversations.md
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
│   ├── prompts/
│   │   └── IMPLEMENT_GARMENT_INTELLIGENCE.md
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
| Cache/coordination | **Valkey 8.x** using the Redis-compatible protocol | Independently selected hot-cache, bounded-concurrency, and rate-limit adapters. Never treat Valkey as authoritative. |
| Task queue | **Celery 5.x** or **QStash** behind a `JobDispatcher` port | Broker/delivery configuration is separate from general Valkey use; PostgreSQL job intent and checkpoints are authoritative. RabbitMQ remains a broker-only Celery migration option. |
| Object storage | **S3-compatible port** with a **boto3** adapter | MinIO locally, S3 on AWS, provider-neutral key/metadata/presign semantics in the application port. |
| Image processing | **Pillow** plus **opencv-python-headless** | Decode/bomb limits, EXIF orientation, sRGB normalization, dimensions, blur/brightness/glare, SHA-256, and pHash candidate generation. |
| Barcode decoding | **OpenCV where sufficient, otherwise one small reviewed decoder** | Decode locally before AI/OCR fallback; validate supported formats/checksums. Select an extra package only after maintenance/license/native-image checks. |
| Provider HTTP | **httpx** | Timeouts, bounded concurrency, request fingerprinting, OpenAI-compatible endpoint, no provider SDK in domain code. |
| Product information | **Provider-neutral `ProductInformationProvider`; `httpx` remains inside the HTTP JSON infrastructure adapter** | Deterministic no-network mock by default; sourced real adapters later; explicit SSRF/outbound URL policy. |
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

Phases 10–13 form one coordinated breaking core release. They may be developed
as reviewable commits, but the cutover is not accepted or released after only
the upload/revision change. The release completes only when the rich evidence,
planner/validator, and rich result replace the old analysis path and all legacy
roles/contracts/code are removed.

## Phase 10 — Multi-photo upload and analysis revisions

- **Objective:** Replace the two-photo/one-result contract with the revision-aware
  multi-photo contract as an intentional breaking cutover.
- **Scope:** Support one to eight completed images by default with repeated
  `garment_overview`, `care_label`, `composition_label`,
  `barcode_brand_label`, `stain_closeup`, `damage_closeup`,
  `construction_detail`, and `other` roles; add image collection operations,
  ordering/removal, an accessible Expo gallery, and revision-aware analysis.
- **Explicitly excluded:** Rich AI evidence, care planning, product-network
  lookup, identity matching, and chat behavior.
- **Database changes:** Add a new Alembic revision after current head; expand the
  image-role constraint and metadata; add minimal physical `garments`,
  `analysis_revisions`, active revision/result pointers, revision-trigger image
  membership, and supersession fields. Transform retained local rows where useful,
  then remove obsolete one-extraction/result-per-scan constraints and legacy
  image-role/result columns; do not implement dual schemas.
- **API endpoints:** Replace the current create-with-images contract so
  `POST /api/v1/scans` creates only a draft scan; add
  `POST /api/v1/scans/{id}/images` and
  `DELETE /api/v1/scans/{id}/images/{image_id}`; return typed image/revision
  metadata. Regenerate OpenAPI/client atomically.
- **Frontend:** Replace the fixed two-slot state with an accessible gallery,
  repeated roles, camera-first add, upload fallback, preview/reorder/remove, per-
  role guidance, count/size limits, and retry states.
- **Tests:** One/eight/over-limit images, repeated roles, order/removal,
  incomplete upload, tenant ownership, object deletion, explicit rejection of
  removed legacy roles/contracts,
  migration empty/previous-head, generated contract, web and Android capture.
- **Acceptance:** Legacy fixed-role requests are unsupported; eight repeated-role
  images can be uploaded and analyzed as one revision; adding/removing evidence
  creates/supersedes a revision rather than using the old one-result model.
- **Validation:** Targeted backend/frontend tests, migration tests,
  `make openapi`, `make lint`, `make test`, Android development-build smoke, and
  `make check`.
- **Suggested commit:** `feat(scans): support multi-photo analysis revisions`

## Phase 11 — Rich source-referenced evidence dossier

- **Objective:** Replace the narrow `LabelExtractionPayload` boundary with a
  multi-photo garment evidence contract that is independent of application and
  infrastructure modules.
- **Scope:** Create domain evidence types for image observations, garment
  category/construction, photographed care and composition facts, materials,
  barcode/brand observations, visible stain/damage hypotheses, original text,
  uncertainty, confidence, and evidence source IDs. Add deterministic merge of
  an evidence delta into immutable/superseding observations.
- **Explicitly excluded:** AI care proposal, external product lookup, customer
  rich prose, automatic identity linking, and chat.
- **Architecture migration:** Remove the reverse dependency where domain
  `care.py` imports `application.vision`; provider Pydantic DTOs map into domain
  evidence at the application boundary. Remove the legacy narrow provider/domain
  mapper rather than retaining a compatibility adapter.
- **Database changes:** Add revision-owned evidence dossiers, observations,
  source references, stable-versus-time-varying classification, and safe raw/
  validated snapshots. Do not overwrite historical `label_extractions`.
- **Provider changes:** Evolve the provider port to `extract_evidence(images,
  prior_dossier)`; pass image IDs and roles; update mock, OpenAI-compatible,
  Responses, and Azure adapters plus operation/prompt/schema metadata.
- **Tests:** Multiple/repeated roles, per-fact provenance, label text fidelity,
  composition tolerances, unknowns, garment-only provisional state, stain
  hypotheses, prompt-injection text, delta merge/supersession, adapter contracts,
  and deterministic fixtures with no network by default.
- **Acceptance:** Every fact is source-referenced; absent evidence stays unknown;
  visible stain identity is not asserted as certain; a complete active dossier
  can be reconstructed from persisted revisions without provider state.
- **Suggested commit:** `feat(evidence): add multi-photo garment dossier`

## Phase 12 — AI care planning and deterministic validation

- **Objective:** Let AI propose the rich answer while retaining an immutable
  deterministic release gate for every safety-relevant claim.
- **Scope:** Add `CarePlanningProvider`, strict `ProposedCarePlan`, separate
  detergent proposal, `CareValidationReport`, versioned validator policies,
  checksums/activation, accept/warn/block/better-image/review outcomes, and one
  constrained retry using machine-readable repairable violations.
- **Plan sections:** Preparation, stain treatment, cleaning, detergent, drying,
  ironing, professional care, prohibited actions, evidence references,
  uncertainty, rationale codes, and follow-up questions.
- **Hard validation:** Photographed label over catalog/material/generic advice;
  prohibition over allowance; no detergent when water washing is prohibited; no
  excessive temperature; no prohibited bleach/tumble/iron/dry-clean; no consumer
  professional solvents; garment-only remains provisional; sensitive materials,
  contradictions, unsupported certainty, and invalid evidence references block
  or route to review.
- **Migration:** Delete `decide_care()` and the narrow v1 result/render execution
  path when this phase lands. Persist proposal and validation report separately and tie
  the active result to their schema/prompt/model/validator versions.
- **Tests:** Table/property-driven every violation/warning/outcome, retry once
  only, second failure review, deterministic validator snapshots, proposal schema
  failures, label/catalog conflicts, stain uncertainty, sensitive materials,
  professional-only wording, and explicit absence of legacy fallback behavior.
- **Acceptance:** A proposal is never customer-visible as approved until the
  complete merged dossier and plan pass the active validator; the validator does
  not silently create another recommendation.
- **Suggested commit:** `feat(care): validate AI-proposed care plans`

## Phase 13 — Rich multilingual result experience

- **Objective:** Present the complete validated dossier and plan clearly in
  Spanish and English.
- **Scope:** Typed result contract and versioned rendering for warnings first,
  preparation, cleaning, stain guidance, materials/construction, photographed
  label facts, sourced product facts, detergent, drying, ironing, professional
  care, prohibited actions, evidence/confidence, uncertainty, validation status,
  and change summary. Optional generated explanation may only restate validated
  claims; structured sections remain present.
- **Database changes:** Revision-aware rendered answers with evidence/proposal/
  validation/template versions and durable source display metadata.
- **Frontend:** Accessible rich result cards, source badges (`photographed`,
  `catalog`, `user`, `visual hypothesis`, `human`), provisional/review states,
  analyzed-before/cleaned-before placeholders, and add-photo/follow-up entry
  points that remain disabled until owning phases.
- **Tests:** ES/EN catalog parity, source labels, numeric/prohibition invariants,
  optional prose claim coverage, screen-reader order, dynamic type, keyboard web,
  snapshots, generated API drift, web E2E, Android result smoke.
- **Acceptance:** Users can understand what was seen, retrieved, inferred,
  proposed, validated, prohibited, and still unknown; no prose changes a
  validated temperature or permission.
- **Suggested commit:** `feat(results): render rich validated garment guidance`

## Phase 14 — Durable garment identity and service history

- **Objective:** Recognize previously handled physical garments without merging
  another unit of the same product or another customer's history.
- **Scope:** Add `exact_instance`, `probable_instance`, `same_product`,
  `visual_candidate`, `new_garment`, and `identity_conflict`; verified
  FabricAssist QR/serial and confirmed relationships; candidate reasons and
  explicit confirmation; stable identity/care versus time-varying condition;
  append-only planned/performed/completed service events.
- **Database changes:** Expand `garments`; add `garment_identifiers`, confirmation
  audit, candidate/match runs, observation relationships, and
  `garment_service_events`. Every tenant-owned row has `tenant_id` and indexes.
- **API/frontend:** Garment list/detail/history, candidate read/confirm/link,
  optional FabricAssist identifier display/scan, analyzed-before versus
  cleaned-before, last analysis/service, and visible change summary.
- **Incremental behavior:** Exact/confirmed garment loads the prior dossier;
  extraction processes only uncached new images; stable evidence is reused;
  condition is appended; the entire merged plan is revalidated.
- **Tests:** Exact tag, prior confirmation, barcode-only same product, identical
  garment false positive, cross-user/tenant denial, conflict handling,
  confirmation idempotency, new stain revision, analysis-versus-service truth,
  deletion/retention relationships, and no vector auto-link.
- **Acceptance:** Only exact instance evidence auto-links; all non-exact matches
  require confirmation; the UI never claims cleaning occurred from an analysis
  or recommendation alone.
- **Suggested commit:** `feat(garments): add identity and service history`

## Phase 15 — Barcode and trusted product enrichment

- **Objective:** Decode garment identifiers and enrich the dossier with sourced
  product data without making the AI a barcode database.
- **Scope:** Deterministic local decode/normalization/checksum validation; OCR/AI
  fallback only for locating/recovering printed digits; provider-neutral
  `ProductInformationProvider`; deterministic exact/probable/ambiguous/not-found
  mock; durable lookup cache; real adapters only after source licensing/privacy/
  coverage review.
- **Database changes:** `product_profiles`, `product_identifiers`, and
  `product_lookup_runs` with provider/source/reference/license metadata, match
  status, request fingerprint, retrieved/refreshed/invalidated times, schema
  version, safe raw/validated snapshots, and variant fields.
- **Security:** No automatic arbitrary QR URL fetching; enforce HTTP(S), allowed
  hosts, DNS/IP checks, private/loopback/link-local denial, redirect and response-
  size limits, timeouts, content-type validation, log redaction, rate/concurrency
  controls, and untrusted-content prompt isolation.
- **Merge policy:** Photographed written/symbol label > exact manufacturer variant
  > verified catalog > material/visual/generic advice. Ambiguity/not-found is
  nonfatal; conflicts create warnings/review and never weaken a prohibition.
- **Tests:** Supported/invalid checksum, blurred fallback, exact/probable/multiple/
  missing, variant conflict, label override, provider timeout/retry, durable
  refresh/invalidation, SSRF/redirect/oversize/malicious content, contract mock,
  and no paid/default network.
- **Acceptance:** A sourced product section appears only with match/source/
  retrieval status; lookup failure leaves image-led analysis functional; barcode
  match does not auto-attach physical garment history.
- **Suggested commit:** `feat(products): enrich garments from trusted barcodes`

## Phase 16 — Server-owned contextual conversation

- **Objective:** Let users ask follow-up questions using garment images, active
  dossier/plan, prior answers, and confirmed service history without provider
  lock-in.
- **Scope:** PostgreSQL threads/messages/versioned rolling summaries; bounded
  `ConversationContextBuilder`; structured assistant text, actionable claims,
  evidence references, uncertainty, and follow-up questions; queued/processing/
  completed/blocked/review/failed states; relevant-image selection; one
  constrained retry only where policy permits.
- **Database changes:** `conversation_threads`, `conversation_messages`,
  `conversation_summaries`, message validation/report references, model-run
  operation metadata, cursor indexes, retention/deletion/audit fields.
- **API/frontend:** Cursor-paginated `GET/POST /scans/{id}/messages`, idempotent
  message submission, polling with future SSE compatibility, localized chat UI,
  revision/source indicators, add-new-photo workflow, clear provisional/blocked
  states, rate limits.
- **Safety:** Every actionable claim uses the active complete dossier and passes
  the same validator. Provider conversation IDs are optimization metadata only;
  label/catalog/user text cannot grant tools or override system/validator policy.
- **Tests:** Prior-answer context, rolling-summary bounds/versioning, relevant
  image resend only, label contradiction, prompt injection, evidence reference,
  stale revision, new-photo activation, duplicate message, worker/provider
  timeout, tenant/ownership, deletion/retention, cost/token metrics.
- **Acceptance:** A follow-up can reference prior images/answers and new evidence;
  each assistant answer records its evidence/result revision and validation state;
  PostgreSQL alone can reconstruct the conversation.
- **Suggested commit:** `feat(chat): add validated garment conversations`

## Phase 17 — Evidence, product, and result reuse

- **Objective:** Avoid repeat provider work without confusing cache, product
  identity, and physical garment memory.
- **Scope:** Versioned normalized SHA-256 exact evidence cache; pHash candidate
  discovery; canonical validated-plan signature; durable product lookup refresh;
  rendered answer cache; Valkey hot mirrors; reuse/invalidation/provenance/count;
  incremental evidence delta selection.
- **Explicitly excluded:** Cross-tenant physical history, automatic pHash/vector
  identity, semantic override of exact safety facts.
- **Tests:** Exact new/old image combinations, schema/prompt/validator/product/
  template mismatches, crossed-symbol false candidates, tenant isolation, Valkey
  loss, concurrent reuse, product refresh, full merged-plan revalidation, and
  provider spies proving only new uncached evidence is extracted.
- **Acceptance:** A remembered garment with one new stain image reuses stable
  dossier facts, calls vision only for the new image where safe, replans affected
  guidance, and validates the entire resulting plan; Valkey loss loses no record.
- **Suggested commit:** `feat(cache): reuse versioned garment evidence safely`

## Phase 18 — Review, history, deletion, and retention

- **Objective:** Complete operator correction and privacy lifecycle for garments,
  analyses, products, conversations, and service history.
- **Scope:** Review queue/detail/assignment; immutable human-corrected evidence;
  planner rerun and deterministic revalidation; approval/audit; customer feedback;
  garment/scan history; retained-image previews; idempotent deletion/outbox;
  conversation/product association policy; object deletion/retention jobs.
- **API/frontend:** Existing review endpoints plus garment history, service-event
  confirmation, feedback, deletion states, and operator source/proposal/validator
  inspection. Product source cache may remain generic only under documented policy;
  personal links/history are removed.
- **Tests:** Role/tenant isolation, correction supersession, validation rerun,
  approval idempotency, analyzed/cleaned truth, cursor history, duplicate delete,
  object/provider transient failures, conversation purge, garment association
  cleanup, audit redaction, retention boundary, Playwright operator/customer flow.
- **Acceptance:** Original evidence/proposals remain auditable; approved correction
  creates a new validated revision; deletion eventually removes private objects
  and personal conversation/history associations according to policy.
- **Suggested commit:** `feat(review): complete garment review and lifecycle`

## Phase 19 — Observability, deployment, and production hardening

- **Objective:** Prove the expanded product is secure, observable, portable, and
  operationally recoverable before production use.
- **Scope:** Correlation/traces across image, identity, product lookup, planning,
  validation, chat, review, and deletion; structured redacted logs; rate and
  global/tenant concurrency limits; metrics for identity outcomes, lookup
  coverage/conflicts, validator blocks/retries, conversation context/cost, and
  reviews; explicit CORS/security headers; provider/subprocessor/privacy docs;
  OpenTofu AWS staging; backup/restore, outage, Valkey loss, worker crash, SSRF,
  load, accessibility, Android/iOS release gates.
- **Tests/validation:** Full `make check`, clean Compose migrate/seed/smoke,
  previous-head migrations, provider/product/chat fixture evaluation, E2E and
  Android smoke, security/secret/dependency/container/IaC scans, controlled load,
  backup/restore and failure drills.
- **Acceptance:** Expanded acceptance criteria in requirements are demonstrated;
  no unreviewed high/critical vulnerability; textile-care validator, product
  source/licensing, privacy/retention, and rollback approvals are recorded; local
  operation still requires no paid provider or proprietary catalog.
- **Suggested commit:** `chore(release): harden garment intelligence platform`

# 6. Testing strategy

All default suites are deterministic and use synthetic or appropriately licensed
fixtures. Network access to paid providers is denied or unconfigured by default.

## Unit tests

- Domain enums/value objects, scan/revision transitions, evidence delta merging,
  identity classification, product normalization, proposed plans, validation
  outcomes, conversation context, permissions, idempotency, signatures,
  translation parameters, and review logic.
- Application services use in-memory/fake ports and explicit clocks/UUID sources;
  infrastructure behavior belongs in integration/contract suites.
- Use table-driven tests for finite safety branches and Hypothesis selectively
  for invariants such as “prohibition cannot pass allowed advice” and “incremental
  evidence still validates the complete merged plan.”

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
- Exercise only the new contract plus explicit rejection of removed legacy
  request/result shapes and provider/internal data redaction.
- Cover multi-photo collections, identity confirmation, product source metadata,
  rich results, messages, and service events with generated client parity.

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
- Cover new-image-only extraction, evidence merge, product lookup, one proposal
  retry, chat claims, stale revisions, and activation of the validated revision.

## Frontend component tests

- React Native Testing Library covers auth forms, multi-photo capture/gallery,
  upload and polling states, source-aware rich results, identity confirmation,
  analyzed/cleaned history, product lookup states, contextual chat,
  provisional/uncertain banners, review, deletion, and platform adapters.
- Test accessible labels, focus/keyboard behavior for web, dynamic text, screen
  reader order, and meaning independent of color.
- Mock generated API transport, not hand-written response types.

## End-to-end tests

- Playwright web critical path: register/login → multi-photo direct MinIO upload
  → analyze with mock → rich result ES/EN → recognize/confirm repeated garment →
  add new stain evidence → sourced mock barcode enrichment → validated follow-up
  chat → exact/incremental reuse → request review → correction/approval →
  analyzed/cleaned history → deletion.
- Cross-tenant negative flows run with separate browser contexts.
- Maestro provides at least an Android development-build smoke for auth, camera/
  selection, upload, processing, result, and logout. iOS CI is added on an
  available macOS runner.

## LLM fixture-based tests

- Version fixtures for clear/incomplete labels; multi-photo repeated roles;
  blur/glare/folds/crop/low
  resolution; Spanish/English/mixed/original other-language text; written
  supplements; contradictions; dry-clean-only/do-not-dry-clean; wool/silk/
  technical/leather/suede/fur; unknown symbols/fields; garment-only/unrelated;
  visible stain hypotheses; barcode/brand/model; product exact/ambiguous/missing/
  conflict; identity candidates; incremental deltas; chat injection/conflicts.
- Expected data asserts normalized source-referenced evidence, plan constraints,
  validator outcome, identity/product status, unknowns, and confidence ranges,
  not brittle provider prose.
- The mock returns these fixtures exactly. The OpenAI-compatible adapter uses an
  in-process synthetic HTTP server/transport. Live evaluation is opt-in and
  cannot gate ordinary pull requests unless separately funded/approved.

## Care-plan validator regression tests

- One case for every care/detergent validator branch, photographed-label/catalog/
  material precedence, all prohibited combinations, professional-only handling,
  sensitive category, stain uncertainty, unknown, contradiction, invalid source
  reference, chat claim, and retry outcome.
- Activated fixture outputs and checksums are immutable. A new version adds new
  fixtures rather than overwriting old expected history.
- Verify rendering/conversation cannot alter permissions or numeric temperatures
  or introduce an actionable claim not present in the validated plan.

## Image test fixtures

- Programmatically create simple safe fixtures where possible; repository images
  must have a source/license manifest and contain no real customer data.
- Include dimensions/size/format/EXIF/metadata, malformed and decompression-bomb
  simulations that are safe for CI, quality signals, normalization SHA, pHash
  candidate behavior, repeated roles, garment/label/composition/barcode/stain/
  damage classification, and identity false-positive fixtures.
- Never copy protected official symbol artwork without confirmed rights.

## Cache-reuse tests

- Prove exact compatible repeat causes no additional provider invocation and a
  remembered garment with one new image extracts only the new image where safe.
- Prove schema, normalization, rules, detergent, template, language, invalidation,
  tenant, prohibition, temperature, process-letter, and warning mismatches miss.
- Prove pHash/semantic candidates cannot become hits without exact safety field
  comparison; Valkey flush falls back to PostgreSQL; concurrent hits update
  provenance safely.
- Prove product lookup refresh/invalidation and full merged-plan revalidation are
  independent of Valkey.

## Security and tenant-isolation tests

- For every tenant-owned API/repository, create user A/tenant A, user B/tenant A,
  and user C/tenant B and assert role plus ownership behavior.
- Cover registration/login rate limits, enumeration resistance, Argon2id, refresh
  rotation/replay, CSRF/cookie/CORS, idempotency ownership, object key/URL scope,
  upload MIME/size/decode/bomb defense, log/audit redaction, preview expiry,
  operator/admin restrictions, and eventually consistent deletion.
- Cover identity-candidate privacy, product adapter SSRF/redirect/size/content
  controls, prompt injection from image/catalog/chat text, chat/service ownership,
  and analyzed-versus-cleaned audit truth.
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
  evidence/planner/chat provider/model/timeout/concurrency, product-information
  provider/outbound policy, maximum image count, conversation context bounds,
  JWT/refresh hash keys, retention/upload limits, OTEL, and log level under that
  prefix.
- `FABRICASSIST_EVIDENCE_PROVIDER=mock`,
  `FABRICASSIST_CARE_PLANNER_PROVIDER=mock`, and
  `FABRICASSIST_CHAT_PROVIDER=mock` are the local/default test values.
- The API lifespan runs bounded PostgreSQL-authoritative recovery for
  analysis/conversation publication and object deletion in both Celery and
  QStash topologies; it requires no hosted scheduler in default tests.
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
   PostgreSQL+pgvector, Valkey, MinIO, and worker; evidence/planning/product/chat
   contract fixtures and coverage; live providers excluded.
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
5. **Rollback:** the garment-intelligence release is coordinated and does not
   support mixed old/new clients. Restore a pre-cutover database snapshot plus
   matching API/worker/web digests only when the reviewed runbook explicitly
   supports it; otherwise prefer a forward fix. Document object/validator/template
   version boundaries.

# 9. Risks and mitigations

| Risk | Mitigation and verification |
|---|---|
| Incorrect care-symbol interpretation | Preserve original evidence; strict codes/confidence/unknowns; contradiction checks; textile expert review of rules/fixtures; sensitive/prohibition cases route to review; never claim engineering tests prove textile correctness. |
| LLM hallucinations | Strict evidence/proposal/chat schemas and source references; missing evidence is `unknown`; deterministic validator gates every actionable claim; one constrained retry only; blocked/review fallback; fixture/provider promotion gate. |
| Incompatible cached result reuse | Version normalization/evidence/proposal/validator/product/template/context keys; tenant scope; exact safety-field comparison; pHash/vector are candidates only; invalidation/provenance; full merged-plan revalidation. |
| Wrong physical garment match | Separate product and physical garment; auto-link only verified instance IDs/prior confirmations; require confirmation for barcode/product/visual candidates; tenant/user scope; false-positive fixtures and unlink audit. |
| Incorrect or missing barcode data | Deterministic normalization/checksum, typed exact/probable/ambiguous/not-found outcomes, source/retrieval display, physical label authority, mock default, catalog conflict tests. |
| Malicious QR/catalog target | Do not fetch arbitrary URLs; HTTP(S)/host/IP/redirect/size/timeout/content policy, SSRF tests, outbound network restriction, untrusted content isolation and log redaction. |
| Stale or unsafe conversation context | PostgreSQL revision ownership, versioned bounded summaries, recent-message/token limits, relevant images only, stale-revision detection, claim validation, deletion and prompt-injection tests. |
| Blurred or incomplete labels | Pre-provider quality signals and thresholds; actionable retake guidance; stop unusable input before paid call; uncertainty/review fallback; quality fixture set with configurable tested thresholds. |
| Personal data in uploaded images | Private buckets/URLs, EXIF stripping on normalized derivatives, no image/request logging, short retention/default 30 days, deletion workflow, provider retention/privacy review, tenant isolation, least privilege, encryption and documented data flow. |
| High image-storage cost | Configurable retention/lifecycle expiry, normalized derivatives sized for inference, no DB blobs, deletion retry, bucket metrics/budgets, avoid duplicate originals where privacy policy allows only through references—not unsafe shared access. |
| Long-running AI requests | Async jobs, client polling, hard provider timeout, global/per-tenant concurrency, persisted stages, bounded retries/backoff/jitter, p95 metrics, no long HTTP request, cancellation/failed visibility. |
| Provider outages | Provider-neutral port, mock/local compatibility, categorized retry, circuit/concurrency controls, queue backpressure, operator retry action, cached validated results where safe, outage runbook, no fabricated fallback answer. |
| Mobile/web camera differences | Small `.native`/`.web` adapters, shared business/UI states, file-library fallback, platform permissions, device/emulator/browser matrix, clear guidance, no scattered `Platform.OS`. |
| Trademark/licensing restrictions for care-symbol artwork | Use text/original generic shapes until rights are confirmed; record fixture/artwork provenance and license; do not copy protected official symbol sets; legal/domain approval gate before branded artwork. |
| Tenant data leakage | `tenant_id` in every business table, tenant criteria inside repositories, role/ownership tests for every route, private object prefixes and scoped presigns, tenant-scoped cache default, audit and metric isolation. |
| Unsafe validator change | Immutable activated versions/checksums, new version rather than mutation, exhaustive regression fixtures, textile expert approval, result/signature/version provenance, rollback-compatible activation. |
| Valkey loss or duplicate Celery delivery | PostgreSQL state/checkpoints authoritative; idempotency keys and constraints; short expiring lock only as optimization; redispatch/recovery tests; durable results/cache mappings in PostgreSQL. |
| Deletion partial failure | Transactional request/outbox state, idempotent object deletion task, retry/visibility/audit, tombstone and association policy, retention reconciliation job and runbook. |
| Dependency/version drift | Lockfiles and pinned images/actions, generated-client drift, Renovate/Dependabot review, SBOM/vulnerability/license scans, Expo compatibility checks and upgrade smoke. |
| PostgreSQL/provider/cloud lock-in | Standard SQL/JSON/S3/HTTP/OTLP/container boundaries, AWS only in adapters/IaC, pgvector inside authoritative DB but optional for MVP, export/backup/restore drills. |
| Cost or latency abuse | Authentication/scan/upload/analysis rate limits, file limits, idempotency, concurrency quotas, model/token/cost metrics, budgets and admin summaries. |

# 10. Definition of done

## Global definition of done

FabricAssist MVP is done only when:

1. The complete customer and operator flows satisfy all MVP acceptance
   criteria in the requirements locally with Docker Compose and in staging.
2. Evidence, proposed plans, and actionable chat claims are strict typed data;
   deterministic versioned Python validators gate every released care/detergent action.
3. Prohibitions, contradictions, garment-only cases, low confidence, and
   sensitive materials fail safely and have exhaustive regression coverage.
4. PostgreSQL is authoritative; Valkey loss cannot erase completed data; images
   remain private in S3-compatible storage and are removed by the retention/
   deletion workflow.
5. Authentication, rotating refresh sessions, role/tenant/ownership enforcement,
   rate limits, CORS, secrets, log redaction, and audit/privacy controls pass
   negative tests.
6. Spanish and English accessible web/mobile results preserve validated facts,
   show provenance/uncertainty, and never rely on free-form prose alone.
7. Exact/incremental evidence, product, canonical result, and render reuse avoid
   repeat provider work while recording provenance/versions and revalidating the
   complete merged plan.
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
16. Product profiles and physical garments are separate; non-exact identity
    candidates require confirmation; analyzed-before and cleaned-before are truthful.
17. Product lookups are sourced, safe under ambiguous/not-found/conflict cases,
    and photographed care-label facts remain authoritative.
18. PostgreSQL can reconstruct garment evidence revisions, validated plans,
    conversations, and confirmed service events without provider-side memory.

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
- [ ] README/configuration/environment/security/retention/validator/cache/provider
      documentation changed with behavior.
- [ ] No secrets, private customer data, unsafe logs, unlicensed fixtures, or
      floating dependencies were introduced.
- [ ] Acceptance criteria are demonstrated and the completion report lists files,
      commands/results, migration/env instructions, and remaining risks.
- [ ] The commit is focused, buildable, and uses the suggested imperative format.

# 11. Recommended first implementation task

The repository foundation and narrow local analysis slice already exist. The next
Codex session should implement the coordinated **Phases 10–13 breaking core
cutover**. It must not release or present Phase 10 alone as the new architecture.

The exact task is:

> Starting from the existing working tree, replace create-with-fixed-images scans
> with draft scan creation plus an image collection supporting a configurable
> default maximum of eight
> images with repeated typed roles. Add analysis revision persistence and active
> revision pointers through a new Alembic migration; add image collection API
> operations; replace the fixed Expo two-slot state with an accessible
> camera-first gallery; regenerate OpenAPI/client; remove legacy role/request/
> result compatibility instead of adding shims; add backend/frontend/migration/
> contract tests; then implement the source-referenced evidence dossier, strict
> AI-proposed plan, deterministic validator, and rich multilingual result from
> Phases 11–13. Delete the narrow extraction/result/renderer and `decide_care()`
> execution rather than retaining fallbacks. Run all relevant quality gates. Do
> not begin garment identity matching, product lookup, or chat.

That is the smallest coherent breaking vertical slice because every later feature
depends on a revision-aware multi-photo aggregate and the user explicitly does
not want the old analysis mode kept for compatibility. The reusable detailed
handoff prompt is in `docs/prompts/IMPLEMENT_GARMENT_INTELLIGENCE.md`.
