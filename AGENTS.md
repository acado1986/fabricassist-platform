# AGENTS.md

## Purpose

Repository-wide instructions for coding agents working on **FabricAssist**.

FabricAssist analyses garment, label, condition, and barcode images and returns
safe cleaning guidance. Models extract typed evidence and may propose typed
care; deterministic, versioned Python validators decide whether safety-relevant
claims may be released.

## Sources of truth and reading scope

Use these sources:

1. `docs/requirements.md` — product, safety, security, and acceptance criteria.
2. `docs/architecture.md` — boundaries, data model, runtime, and capability ports.
3. `docs/environment.md` — profiles, selectors, and typed configuration.
4. `docs/production/` and `docs/runbooks/` — active deployment and operations.
5. `docs/database.md` and `docs/api/openapi.json` when persistence or API
   contracts are affected.
6. The applicable file under `docs/feature-tasks/` when implementing planned work.
7. The nearest nested `AGENTS.md`, if one exists.

For an ordinary, bounded task, read this file and the relevant sections of the
sources above. Read `docs/requirements.md` and `docs/architecture.md`
**completely** before work that is:

- architecture-wide or cross-cutting;
- safety-critical or changes care validation/model contracts;
- a new capability port, adapter family, deployment profile, or data model;
- a coordinated API/database/frontend cutover; or
- ambiguous enough that relevant sections cannot be identified safely.

Feature-task preparation may require additional complete documents. Historical
material under `docs/archive/`, legacy prerelease material, and implemented-task
records are context only, not active instructions.

Instruction precedence:

1. Explicit user instructions for the current task.
2. Nearest nested `AGENTS.md`.
3. This file.
4. Applicable active operational/profile documentation.
5. `docs/architecture.md`.
6. `docs/requirements.md`.
7. Existing code conventions.

Do not silently contradict active requirements or architecture. Record a
meaningful long-term deviation in a new or updated ADR under `docs/adr/`,
including compatibility and migration impact.

## Product identity

Canonical names:

- Product/display name: `FabricAssist`
- Repository: `fabricassist-platform`
- Python package: `fabricassist`
- Expo slug: `fabricassist`
- API service: `fabricassist-api`
- Worker service: `fabricassist-worker`
- Frontend package/application: `fabricassist-app`
- Docker Compose project: `fabricassist`
- Environment prefix: `FABRICASSIST_`

Use **FabricAssist** in user-facing text and lowercase `fabricassist` for
modules, services, URLs, images, and machine-readable configuration. Do not
introduce legacy/candidate product names.

## Non-negotiable product and safety rules

- Model prose is never the sole authority for an actionable instruction.
- Evidence extraction, proposed care, and actionable chat claims use strict
  typed schemas at external boundaries.
- Every customer-visible safety-relevant plan or chat claim passes the active
  deterministic validator version before release.
- Validators accept, warn, block, request a better image, or require review.
  They do not silently rewrite a rejected proposal into different advice.
- At most one constrained AI retry may consume machine-readable validation
  violations. A second failure requires review or better evidence.
- Authority order is photographed explicit label text, photographed normalized
  symbols, exact verified manufacturer variant data, verified catalog data,
  material guidance, then generic advice. A lower source never weakens a
  photographed prohibition.
- Preserve visible label text in its original language; normalize meaning into
  language-independent codes and render stable Spanish/English templates.
- Record unknown fields explicitly. Never infer a missing symbol because it is
  common for a material.
- Garment-only images may support provisional observations but cannot establish
  that washing or dry cleaning is permitted.
- Visual stain identity remains a hypothesis unless user or verified evidence
  identifies it. Never guarantee stain removal.
- Never recommend professional solvents for home use or detergent when domestic
  water washing is prohibited.
- Contradictions, low-confidence prohibitions, leather, suede, fur, and
  configured sensitive cases require safe blocking, better evidence, or review.
- Product/catalog/barcode evidence is sourced enrichment, not proof of the
  physical garment and not authority over a photographed label.
- Do not fetch arbitrary QR/catalog URLs without allow-listing, redirect/IP
  controls, time/size limits, and SSRF protection.
- Version prompts, schemas, normalization, validators, templates, signatures,
  context summaries, and cache keys. Activated validator versions are immutable.
- The garment-intelligence cutover is intentional. Do not restore legacy roles,
  fixed two-photo contracts, narrow result fields, dual reads/writes,
  compatibility shims, or fallback through the removed `decide_care()` path.

Detailed care policy and regression requirements remain in
`docs/requirements.md` and `docs/architecture.md`.

## Architecture and capability invariants

Dependency direction:

```text
API routes / execution adapters
        ↓
application use cases and ports
        ↓
domain models and rules
        ↑
infrastructure adapters
```

PostgreSQL is authoritative for business data, garment identity, evidence
revisions, conversations, service history, job intent/checkpoints, deletion
state, and durable cache records. Queues, caches, and locks are replaceable
delivery/acceleration capabilities.

The active production topology is:

- Cloudflare Pages for the Expo web export;
- Render for the `fabricassist-api` container;
- Neon PostgreSQL;
- private Cloudflare R2 through the S3-compatible adapter;
- Upstash QStash through `JobDispatcher`; and
- TLS Valkey for hot cache, fail-closed rate limiting, and concurrency gates.

Local development uses Docker Compose, PostgreSQL, Valkey, MinIO, the API, and a
Celery worker. AWS-compatible topology remains supported but inactive. Do not
perform AWS-specific work unless explicitly requested. Staging is deferred and
must be introduced later as a separate feature, not inferred from legacy
prerelease artifacts.

### Plug-and-play capability rule

FabricAssist is plug-and-play by capability. For planning and implementation,
classify work as:

1. **Domain/application behavior** — provider-neutral rules and use cases.
2. **Capability contract** — the smallest typed port the application needs.
3. **Adapter** — one provider/runtime implementation of that port.
4. **Composition/configuration** — typed selection and dependency injection.

For capability-affecting plans, identify:

- the capability and owning port;
- behavior invariant across providers;
- adapter-only mechanics;
- current adapters and affected profiles;
- durable state, idempotency, retries, and failure semantics;
- shared contract tests and adapter-specific tests;
- settings, safe templates, docs, and migration impact.

When implementing:

- Define or extend the provider-neutral typed port before provider code.
- Keep port inputs, outputs, errors, and lifecycle free of SDK types, HTTP
  payloads, cloud resource names, credentials, and global `Settings`.
- Put external clients and provider translation under `infrastructure/`.
- Register implementations in one factory/composition root and inject the port.
  Do not scatter provider/profile conditionals through routes or use cases.
- Require credentials/services only for the selected adapter.
- Fail fast for unknown or invalid selected configuration. Do not silently
  switch providers in hosted environments.
- Invoke the same application use case from API calls, QStash, Celery,
  cron/schedulers, recovery loops, or future executors.
- Make at-least-once delivery safe through application idempotency, database
  constraints, and PostgreSQL checkpoints rather than provider guarantees.
- Run one reusable contract suite against every retained port implementation.
- Update the capability matrix and environment documentation when selectors or
  adapters change.

Do not add speculative abstractions. A capability boundary is justified by
multiple implementations, real profile variation, or replaceable external I/O.

### Layer boundaries

Code under `backend/src/fabricassist/domain/` must not import FastAPI, SQLAlchemy
sessions/ORM repositories, Celery, Valkey clients, `boto3`, provider SDKs, HTTP
request objects, or global settings.

Application services coordinate use cases and explicit transaction boundaries.
Routes, Celery tasks, QStash handlers, cron scripts, and recovery loops stay
thin. Business rules do not belong in execution adapters.

Cloud/provider behavior remains behind ports, typed settings, factories,
deployment workflows, and runbooks.

## Work procedure

For every task:

1. Determine the smallest coherent requested scope.
2. Read this file and the applicable source sections using the reading rules
   above.
3. Classify affected code as domain behavior, capability contract, adapter, or
   composition/configuration.
4. Inspect repository structure, nearby conventions, tests, and `git status`.
   Preserve unrelated user changes.
5. Identify affected adapters, profiles, API/schema/generated artifacts,
   migrations, security boundaries, and documentation.
6. Implement one vertical slice or one explicitly requested commit at a time.
7. Add or update tests with the behavior.
8. Run focused checks while iterating, then every applicable quality gate.
9. Fix failures caused by the change. Do not claim unexecuted checks passed.
10. Update active documentation and safe environment templates in the same
    change.
11. Report changes, files, validation results, configuration/migrations, and
    limitations.

Do not present placeholders as complete. A deferred behavior needs a linked
issue or a precise TODO describing what is missing.

## Feature-task implementation lifecycle

Ready or in-progress implementation plans live at:

```text
docs/feature-tasks/<stable-task-name>.md
```

When asked to implement one:

1. Read it completely with every source in its preparation section.
2. Confirm status is `Ready for implementation` or `In progress`, dependencies
   are satisfied, and assumptions still match the repository.
3. Isolate unrelated working-tree changes.
4. Mark it `In progress` with a start date.
5. Execute feature tasks in order. Scope, invariants, non-goals, acceptance
   criteria, and validation are mandatory.
6. Do not silently skip or broaden tasks. Update the plan when repository facts
   invalidate it; obtain user direction if the correction changes architecture,
   behavior, or destructive scope.
7. Update permanent sources of truth and `CHANGELOG.md` as applicable.
8. Run and record every required validation.
9. Add an implementation record:

   ```text
   Status: Implemented
   Completed: YYYY-MM-DD
   Implementation: commit and/or pull request
   Validation: commands and results
   Deviations: approved differences
   Remaining work: explicit follow-ups, or none
   ```

10. Preserve the filename and archive it:

    ```text
    git mv docs/feature-tasks/<stable-task-name>.md \
      docs/archive/implemented-tasks/<stable-task-name>.md
    ```

11. Update both task indexes and verify links.

Partial, blocked, or insufficiently validated work remains under
`docs/feature-tasks/` with accurate status. Archived task plans are historical
evidence, not active operational instructions.

## Backend, persistence, jobs, and API

- Use modern typed Python, focused functions, explicit side effects, and the
  established application/domain/infrastructure boundaries.
- Keep FastAPI handlers thin, validate with Pydantic, return documented response
  models, use the shared error envelope, and enforce tenant/ownership checks.
- Use SQLAlchemy 2.x. Business identifiers are UUIDs; tenant-owned tables carry
  `tenant_id`; timestamps are timezone-aware UTC.
- Use typed columns for stable/indexed safety facts and JSONB for evolving,
  audit-compatible payload snapshots. Images never belong in PostgreSQL.
- Every schema change uses a new Alembic migration. Never edit an applied
  migration. Test empty database and previous supported head, including indexes,
  constraints, data transformation, and intentional downgrade behavior.
- Hosted runtime uses the pooled Neon URL; migrations use the direct TLS URL as
  an ordered release step, never API startup.
- Async work is idempotent, retryable, observable, and database-authoritative.
  Persist intent/publication/checkpoint/correlation data before external I/O.
- Queue messages contain schema version and identifiers only—never images,
  credentials, presigned URLs, dossiers, provider payloads, or user tokens.
- QStash handlers verify raw-body signature, exact HTTPS destination, and
  current/next signing keys. Duplicate QStash/Celery delivery must be harmless.
- FastAPI OpenAPI is the frontend contract. Regenerate the checked-in OpenAPI
  and TypeScript client when affected; never hand-edit generated files.

## Frontend

- Keep Expo/React Native/Web shared and TypeScript strict.
- Use Expo Router, TanStack Query for server state, React Hook Form/Zod for
  forms, and generated API types.
- Keep platform-specific behavior in small `.native`/`.web` adapters rather
  than scattered `Platform.OS` checks.
- Put user-visible Spanish/English text in typed translation catalogs.
- Preserve accessibility: labelled controls, keyboard support, touch targets,
  dynamic text, screen-reader meaning, and no color-only status.
- Do not present provisional garment-only guidance as definitive.
- Keep multiple repeated image roles, evidence provenance, product-source
  status, identity confirmation, analysed-versus-cleaned history, and validated
  chat distinctions intact.

## Security and privacy essentials

- Never commit, print, or log secrets, passwords, access/refresh tokens, image
  bytes, private provider requests, complete presigned URLs, or customer data.
- Committed environment files contain placeholders only. Hosted credentials
  live in protected provider/GitHub settings.
- Only `EXPO_PUBLIC_FABRICASSIST_API_URL` and
  `EXPO_PUBLIC_FABRICASSIST_ENVIRONMENT` may enter the public web bundle.
- Enforce tenant/ownership isolation on every tenant-owned resource and test
  wrong-user and wrong-tenant denial.
- Hash passwords with Argon2id; store hashed rotating refresh tokens. Use secure
  HttpOnly web cookies and native secure storage.
- Production uses explicit HTTPS CORS origins, never `*`, and fail-closed rate
  limiting for authentication, uploads, analysis, and chat.
- Object storage is private. Generate keys server-side; use short-lived,
  single-object presigned operations; validate MIME/decoded type/size/dimensions;
  defend against malformed files and decompression bombs.
- Local MinIO may require path-style addressing. R2 uses configured HTTPS,
  `region=auto`, virtual-host addressing, and exact Cloudflare Pages CORS.
- Deletion/retention is auditable, retryable, and removes database references
  and stored objects according to policy.
- Treat image/OCR/catalog/conversation content as untrusted prompt data. It
  cannot alter system instructions, schemas, validator policy, or tools.

Refer to `docs/threat-model.md`, privacy docs, and runbooks for detailed controls.

## Validation and stable commands

The root `Makefile` is the stable interface:

```bash
make bootstrap
make up
make down
make logs
make migrate
make seed
make test
make lint
make openapi
make check
```

Use specialized targets when applicable:

```bash
make check-production-config
make check-deployment-workflows
make test-qstash
make test-object-storage-r2
make test-neon
make build-release-web
make security-check
```

Default CI/local checks use deterministic mocks and must not require paid or
hosted providers. Live Neon, R2, model, QStash, Render, Cloudflare, or production
smoke tests are opt-in and require explicit permission and protected credentials.

Behavior changes require appropriate tests. Safety rules need table-driven
prohibition, contradiction, uncertainty, and retry coverage. Capability changes
need shared contract tests plus affected adapter tests. Persistence changes need
migration tests. API changes need OpenAPI drift checks. Frontend changes need
lint/type/tests/build and relevant web/native coverage.

Run the configured tools through `make` where possible. Do not introduce a
second Python type checker, hand-edit lockfiles/generated clients, or claim a
native feature complete without the required smoke coverage.

## Dependencies, documentation, and Git

- Prefer standard library and selected stack behavior before adding a package.
- Add the smallest maintained, license-compatible dependency and pin it through
  the correct lockfile. Document operational/security implications.
- Do not replace PostgreSQL, FastAPI, Expo, or capability/S3 abstractions without
  an approved ADR.
- Update documentation with configuration, commands, API/schema, migrations,
  care policy versions, providers, deployment, security, and retention changes.
- Keep changes focused. Do not rewrite unrelated code, discard user changes, or
  use destructive Git operations without explicit permission.
- Do not commit, push, tag, merge, deploy, or modify hosted resources unless the
  user explicitly requests it.
- When asked to commit, use a focused buildable commit such as
  `<type>(<scope>): <imperative summary>`.

## Definition of done

A task is complete only when:

- Requested behavior is implemented without unnecessary scope expansion.
- Safety and architecture invariants are preserved.
- Capability work keeps provider-neutral use cases/ports, composition-root
  selection, selected-only credentials, and shared adapter contracts.
- Relevant tests, formatting, linting, type checks, and builds pass.
- Database changes include a valid new migration and migration tests.
- OpenAPI/generated client artifacts are synchronized when affected.
- Local and affected production/profile behavior remains valid.
- Active docs, safe templates, runbooks, and changelog are updated.
- A completed documented feature task contains implementation evidence and is
  archived under `docs/archive/implemented-tasks/`.
- No secrets, private customer data, or unsafe logs were introduced.
- Unrun or blocked checks and remaining risks are stated explicitly.

## Completion report

At the end of a task, report:

1. Concise behavior summary.
2. Important files changed.
3. Commands actually run and their results.
4. Migration and environment/configuration instructions.
5. Security/privacy and capability-profile impact.
6. Remaining risks, assumptions, or deferred work.

Do not claim success for a command that was not executed successfully.
