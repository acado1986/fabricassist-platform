# AGENTS.md

## Purpose

This file contains repository-wide instructions for coding agents working on **FabricAssist**.

FabricAssist analyses garment and care-label images and returns safe cleaning instructions. A vision-capable model extracts structured facts; deterministic Python rules produce the authoritative care decision.

## Sources of truth

Before changing code, read these files completely:

1. `docs/requirements.md` — product scope, functional requirements, security requirements, and acceptance criteria.
2. `docs/architecture.md` — selected technologies, module boundaries, data model, runtime architecture, and implementation order.
3. The nearest nested `AGENTS.md`, when one exists.

Instruction precedence is:

1. Explicit user instructions in the current task.
2. The nearest `AGENTS.md` to the file being edited.
3. This root `AGENTS.md`.
4. `docs/architecture.md`.
5. `docs/requirements.md`.
6. Existing code conventions.

Do not silently contradict the requirements or architecture. When a change requires an architectural deviation, add or update an Architecture Decision Record under `docs/adr/` and explain the compatibility and migration impact.

## Product identity and naming

Use these canonical names unless the user explicitly changes the branding:

- User-facing product name: `FabricAssist`
- Repository: `fabricassist-platform`
- Python package namespace: `fabricassist`
- Expo display name: `FabricAssist`
- Expo slug: `fabricassist`
- API service/container: `fabricassist-api`
- Worker service/container: `fabricassist-worker`
- Frontend application/package: `fabricassist-app`
- Docker Compose project: `fabricassist`
- Project-specific environment-variable prefix: `FABRICASSIST_`

Naming rules:

- Write **FabricAssist** in user-facing copy, headings, application metadata, and product documentation.
- Use lowercase `fabricassist` for Python modules, package scopes, service identifiers, image names, URLs, and machine-readable configuration.
- Use `fabricassist-<component>` for deployable service names.
- Do not introduce previous candidate product names or the previous generic project title in new code or documentation.
- Generic domain phrases such as “clothing care assistant” may be used descriptively, but not as the product name.
- Keep naming changes atomic and update application metadata, container names, examples, documentation, and tests together.

## Project principles

- The LLM extracts facts; it does not make the final care decision.
- All model output must be validated by strict Pydantic schemas.
- Final cleaning instructions must come from deterministic, versioned Python rules.
- The label overrides material-based or generic recommendations.
- Missing, contradictory, or low-confidence evidence must produce uncertainty, a better-image request, or human review.
- PostgreSQL is the authoritative system of record.
- Valkey is transient infrastructure and must not be the sole store for completed business data.
- Images belong in private S3-compatible object storage, not PostgreSQL.
- Cloud-specific behavior must remain behind adapters.
- Prefer a modular monolith with separate API and worker processes over premature microservices.
- Keep Android, iOS, and authenticated web functionality in the shared Expo application where practical.
- Favor open protocols and replaceable infrastructure.

## Selected technology stack

### Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic
- PostgreSQL with JSONB and pgvector
- Valkey
- Celery behind a job-dispatch port
- S3-compatible object storage through a storage adapter
- Pillow/OpenCV-compatible image tooling
- `httpx` for external provider calls
- `uv` for Python dependency management
- Ruff for formatting and linting
- Pytest for tests

### Frontend

- Expo
- React Native
- React Native Web
- TypeScript in strict mode
- Expo Router
- TanStack Query
- React Hook Form
- Zod
- Typed Spanish and English translations
- Generated TypeScript API client from FastAPI OpenAPI
- `pnpm` workspaces

### Local infrastructure

- Docker Compose
- PostgreSQL with pgvector
- Valkey
- MinIO or another S3-compatible open-source object store
- API and worker containers

## Repository layout

Expected top-level layout:

```text
.
├── AGENTS.md
├── README.md
├── Makefile
├── .env.example
├── docker-compose.yml
├── backend/
├── frontend/
├── infrastructure/
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   └── IMPLEMENTATION_PLAN.md
└── .github/workflows/
```

Do not introduce a different top-level layout without a documented reason.

## Work procedure

For every task:

1. Read the relevant requirements and architecture sections.
2. Inspect the existing repository before creating files or selecting libraries.
3. State internally the smallest coherent scope that satisfies the task.
4. Implement one vertical slice or one explicitly requested implementation commit at a time.
5. Do not begin later implementation phases unless the user explicitly requests them.
6. Add or update tests with the implementation.
7. Run the relevant validation commands.
8. Fix failures caused by the change.
9. Update documentation when commands, configuration, behavior, schemas, or architecture change.
10. Report what changed, validations run, and any remaining limitations.

Do not leave placeholder behavior presented as complete. Clearly mark intentionally deferred code with a linked issue or a specific TODO explaining the missing behavior.

## Initial implementation order

Follow the commit sequence in `docs/architecture.md` unless the task says otherwise:

1. Repository foundation
2. Backend foundation
3. Frontend foundation
4. Authentication vertical slice
5. Upload vertical slice
6. Async analysis skeleton
7. Care domain
8. Real vision-provider adapter
9. Caching
10. Review and deletion
11. Production readiness

Each step must leave the repository runnable and tests passing.

## Root commands

The root `Makefile` is the stable developer interface. Maintain these targets:

```bash
make bootstrap   # Install or prepare local dependencies
make up          # Start the local Docker Compose stack
make down        # Stop the local stack
make logs        # Follow service logs
make migrate     # Apply database migrations
make seed        # Insert development seed data
make test        # Run all default tests
make lint        # Run formatting, lint, and static checks
make openapi     # Generate OpenAPI and the frontend API client
make check       # Run the complete local quality gate
```

When creating the repository foundation, implement missing targets rather than documenting commands that do not exist.

Prefer non-interactive, deterministic commands suitable for CI.

## Local setup expectations

- Copy `.env.example` to `.env` for local development.
- `.env.example` must contain safe placeholders only.
- Never commit secrets, API keys, tokens, credentials, private URLs, or production identifiers.
- Local startup must not require a paid model API. Use a deterministic mock vision provider by default.
- Paid or live-provider tests must be opt-in and excluded from the default test command.
- Docker Compose must provide health checks and dependency readiness where practical.
- Service names, ports, volumes, and default credentials must be documented in `README.md`.

## Backend architecture rules

Use these dependency directions:

```text
API routes / workers
        ↓
application services and ports
        ↓
domain models and rules
        ↑
infrastructure adapters
```

### Domain isolation

Code under `backend/src/fabricassist/domain/` must not import:

- FastAPI
- SQLAlchemy sessions or ORM repositories
- Celery
- Valkey clients
- `boto3`
- provider-specific SDKs
- HTTP request objects

The domain layer may use standard-library modules and explicitly approved small utility dependencies that do not couple it to infrastructure.

### Application layer

- Coordinate use cases through commands, queries, services, and ports.
- Keep transaction boundaries explicit.
- Do not place business rules in route handlers or Celery tasks.
- Use dependency injection at infrastructure boundaries.

### API layer

- Keep route handlers thin.
- Validate input with Pydantic.
- Return documented response models.
- Use the shared error-envelope format.
- Enforce tenant and ownership authorization on every tenant-owned resource.
- Do not expose provider payloads, internal identifiers, stack traces, or storage keys unnecessarily.

### Persistence

- Use SQLAlchemy 2.x patterns.
- All primary business identifiers must be UUIDs.
- All tenant-owned business tables must include `tenant_id`.
- Use timezone-aware timestamps stored in UTC.
- Use normal typed columns for stable, indexed, safety-relevant facts.
- Use JSONB for original/evolving provider payloads and audit-compatible snapshots.
- Do not use PostgreSQL as an image/blob store.
- Avoid database triggers for domain behavior.

### Migrations

- Create every schema change through Alembic.
- Never edit an already-applied migration to change production history.
- Add a new migration instead.
- Migrations must work on an empty database and on the previous supported schema.
- Prefer expand/migrate/contract changes when rollback compatibility matters.
- Include indexes, constraints, enum/check strategies, and downgrade behavior intentionally.

### Jobs

- Analysis jobs must be asynchronous, idempotent, retryable, and observable.
- The database is authoritative for scan state.
- Use bounded retries with exponential backoff.
- Do not retry deterministic validation failures as transient infrastructure errors.
- Use distributed locks only where idempotency and database constraints are insufficient.
- A worker crash must not leave a scan permanently locked.
- Celery-specific code must remain behind the application job-dispatch boundary.

## AI and care-safety rules

These rules are mandatory:

1. Never use model prose as the authoritative care result.
2. Require structured model output validated by Pydantic.
3. Preserve visible label text in its original language.
4. Normalize meaning into language-independent care codes.
5. Record unknown fields explicitly; do not infer missing symbols.
6. Store provider, model, prompt version, schema version, latency, token usage when available, and estimated cost.
7. Keep provider selection configurable.
8. Support an OpenAI-compatible HTTP adapter, but do not couple domain code to one provider.
9. Never recommend professional cleaning solvents for consumer home use.
10. Never recommend detergent when domestic water washing is prohibited.
11. Do not claim washing or dry cleaning is permitted from a garment-only photograph.
12. Force review for contradictions, low-confidence prohibitions, leather, suede, fur, or other configured sensitive cases.
13. Version prompts, schemas, image normalization, rules, translations, signatures, and cache keys.

### Deterministic rules

- Care rules and detergent rules belong in versioned repository assets and Python domain code.
- Rule changes require regression tests.
- Activated rule versions are immutable.
- The order of authority is:

```text
explicit care-label instruction
    > normalized label symbol
    > material-specific recommendation
    > generic advice
```

### Language handling

- Analyse label text in its original language.
- Store normalized language-independent facts.
- Render final instructions from typed Spanish and English templates.
- Do not translate every request to English before extraction.
- Avoid an LLM translation call for standard instructions that templates can render.

## Cache and memory rules

Implement cache layers in this order:

1. Normalized exact-image SHA-256 lookup.
2. Perceptual-hash candidate lookup.
3. Canonical care-signature lookup.
4. Rendered-answer lookup by language and version.
5. Optional pgvector semantic candidate retrieval after the MVP.

Requirements:

- Cache keys must be namespaced and versioned.
- A cache hit must preserve the source, validation state, rules version, and reuse count.
- Valkey may accelerate reads but must not be the only persistent cache record for validated results.
- Semantic similarity must never override contradictory safety facts.
- Prohibition fields, temperatures, care processes, and rules versions must match before reusing a candidate.
- Engram is not part of the MVP architecture.

## Object-storage rules

- Use private buckets by default.
- Generate object keys server-side.
- Never include a user-supplied path directly in an object key.
- Use short-lived presigned URLs scoped to one object and operation.
- Validate MIME type, actual decoded image type, size, and image dimensions.
- Defend against decompression bombs and malformed files.
- Do not log complete presigned URLs.
- Preserve original images only according to the configured retention policy.
- Deletion must remove both database references and stored objects through an auditable, retryable workflow.

## Frontend architecture rules

- Keep TypeScript strict mode enabled.
- Prefer shared screens and feature components across Android, iOS, and web.
- Isolate unavoidable platform behavior in small adapters such as:

```text
ImageCapture.native.tsx
ImageCapture.web.tsx
SecureSession.native.ts
SecureSession.web.ts
```

- Do not scatter `Platform.OS` checks through business-facing components.
- Use TanStack Query for server state.
- Use Zustand only for small client-only state that does not belong in route state or query state.
- Use React Hook Form and Zod for forms.
- Use Expo Router for navigation.
- Keep user-visible text in translation catalogs.
- Do not hard-code Spanish or English copy inside reusable components.
- Make mobile touch targets accessible and web layouts keyboard accessible.
- Show clear image-retake guidance for blur, crop, glare, and insufficient resolution.
- Do not present provisional garment-only guidance as definitive.

## API contract and generated code

- FastAPI OpenAPI is the source of truth for the frontend API contract.
- Generate the TypeScript client; do not manually duplicate API request/response interfaces.
- Commit generated client code only if the repository convention established in the foundation requires it.
- `make openapi` must be deterministic.
- CI must fail when generated client code or checked-in OpenAPI artifacts drift from the backend schema.
- Do not hand-edit generated files.

## Code style

### Python

- Use modern Python typing.
- Prefer explicit domain types and enums over unstructured dictionaries.
- Use Pydantic models at external boundaries and suitable domain types internally.
- Keep functions focused and side effects explicit.
- Avoid global mutable state.
- Use Ruff formatting and linting.
- Add docstrings when behavior, constraints, or public interfaces are not obvious from types and names.
- Do not catch broad exceptions without re-raising, translating, or logging with safe context.

### TypeScript and React

- Use TypeScript strict mode.
- Prefer function components and hooks.
- Avoid `any`; use `unknown` and narrow it when necessary.
- Keep effects minimal and dependency-correct.
- Prefer composition over large conditional components.
- Do not store derived server data in global client state.
- Use generated API types.
- Keep platform-specific code behind adapters.

### General

- Favor clear code over clever abstractions.
- Do not add a dependency for behavior that is small and safe to implement directly.
- Do not introduce speculative frameworks, agents, vector stores, or microservices.
- Remove dead code created by the change.
- Keep comments focused on why a decision exists, not what obvious code does.

## Dependency policy

Before adding a dependency:

1. Confirm the standard library or selected stack cannot reasonably solve the requirement.
2. Check that the dependency is actively maintained and compatible with the project license.
3. Prefer open-source libraries with standard data formats and protocols.
4. Add the smallest required package, not a broad framework.
5. Pin through the project lockfile.
6. Update dependency documentation when operational configuration is required.
7. Add security-sensitive dependencies only with tests and a clear rationale.

Do not replace PostgreSQL, Valkey, FastAPI, Expo, or the S3-compatible abstraction without an approved ADR.

## Testing instructions

Every behavior change must include appropriate tests.

### Backend default checks

Run from the repository root through `make` where available. Equivalent direct commands may be used while creating the initial Makefile.

Expected checks include:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pytest backend/tests
```

Run the configured static type checker once selected in the repository foundation. Do not introduce both mypy and Pyright unless there is a documented need.

### Backend test expectations

- Unit tests for domain rules and value objects.
- Table-driven tests for every care-rule branch.
- Explicit tests for prohibited and contradictory combinations.
- Integration tests against real PostgreSQL, Valkey, and MinIO containers.
- Provider contract tests with mocked or recorded synthetic responses.
- No paid provider calls in default CI.
- Migration tests from an empty database and the previous schema.

### Frontend default checks

Expected checks include:

```bash
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build:web
```

Use the actual workspace scripts once defined; keep root `make` targets aligned with them.

### Frontend test expectations

- Unit tests for hooks, validation, formatting, and result rendering.
- Component tests for image guidance and care-result states.
- Playwright web E2E coverage for the critical scan flow.
- At least an Android emulator smoke test before claiming a native feature is complete.
- Add iOS CI when an appropriate macOS runner is available.

### AI regression fixtures

Maintain versioned fixtures for:

- Clear and incomplete labels.
- Blur, glare, folds, crop, and low resolution.
- Spanish, English, and mixed-language text.
- Written instructions that supplement symbols.
- Contradictions.
- Dry-clean-only and do-not-dry-clean cases.
- Wool, silk, technical fabrics, leather, and suede.
- Unknown symbols and unknown fields.

Expected fixtures should assert normalized facts and review outcomes, not brittle free-form prose.

## Security and privacy

- Never commit or print secrets.
- Never log passwords, access tokens, refresh tokens, image bytes, complete provider requests containing private images, or complete presigned URLs.
- Hash passwords with Argon2id.
- Store only hashed refresh tokens and rotate token families.
- Apply rate limits to authentication, scan creation, uploads, and analysis.
- Enforce tenant isolation in queries and authorization tests.
- Use secure, HTTP-only cookies for web refresh credentials.
- Use the platform secure store for native refresh credentials.
- Validate CORS explicitly; do not use unrestricted production origins.
- Treat model providers as subprocessors and keep retention configuration documented.
- Use synthetic or licensed images in repository fixtures. Do not commit real customer images.
- Do not reproduce protected care-symbol artwork unless licensing is confirmed.

## Observability

- Emit structured JSON logs.
- Propagate correlation IDs through API, job, model call, and persistence operations.
- Include safe scan, tenant, user, and job identifiers where useful.
- Never include sensitive image or credential data.
- Expose distinct liveness and readiness endpoints.
- Instrument HTTP latency, queue depth, worker duration, retries, model usage, cache hits, review rates, and storage/database errors.
- Prefer OpenTelemetry-compatible instrumentation.

## Documentation

Update documentation in the same change when modifying:

- Local setup or commands.
- Environment variables.
- Public API behavior.
- Database schema or migration procedures.
- Care rules or rule versions.
- Cache-key formats.
- Provider configuration.
- Deployment or operational procedures.
- Security or retention behavior.

Use ADRs for architectural choices with meaningful long-term consequences.

## Git and change discipline

- Keep changes focused on the requested scope.
- Do not rewrite unrelated code.
- Do not perform destructive Git operations unless explicitly requested.
- Do not discard user changes.
- Make each commit buildable and testable.
- Suggested commit format:

```text
<type>(<scope>): <imperative summary>
```

Examples:

```text
chore(repo): add local service foundation
feat(scans): create presigned upload workflow
feat(care): add deterministic washing rules
fix(cache): prevent reuse across rules versions
test(care): cover dry-cleaning contradictions
```

When preparing a pull request:

- Summarize behavior changes.
- List migrations and configuration changes.
- Describe security/privacy impact.
- Provide tests and commands run.
- Identify deferred work explicitly.

## Definition of done

A task is complete only when:

- The requested behavior is implemented without expanding scope unnecessarily.
- Architecture boundaries are preserved.
- Relevant tests were added or updated.
- Formatting, linting, type checks, and relevant tests pass.
- Database changes include valid migrations.
- OpenAPI and generated client artifacts are synchronized when affected.
- Docker/local startup remains functional when affected.
- Documentation and `.env.example` are updated when affected.
- No secrets or private customer data were added.
- The final report names commands actually run and states any checks that could not be run.

## Agent completion report

At the end of a task, provide:

1. A concise summary of implemented changes.
2. The important files changed.
3. Validation commands run and their results.
4. Migration or environment-variable instructions.
5. Remaining risks, assumptions, or deferred items.

Do not claim a command passed unless it was actually executed successfully.
