# FabricAssist — Product and Technical Requirements

**Document status:** Initial implementation baseline  
**Target release:** MVP  
**Primary implementation agents:** Codex and human reviewers  
**Last updated:** 2026-07-20

## 1. Purpose

**FabricAssist** is an independent application for professional cleaning companies and garment owners. It analyses photographs of garments and care labels and returns clear, safe, explainable cleaning instructions.

The product must support Android, iOS, and web from a shared React-based frontend. The backend must be Python-based and must orchestrate vision-capable language models, deterministic care rules, caching, persistence, and human review.

The AI is an extraction component, not the final authority. The final care decision must be produced by a deterministic, versioned rules engine from normalized label facts.

### 1.1 Product identity

Use the following names consistently across source code, infrastructure, documentation, and user-facing interfaces:

- **Product and brand name:** `FabricAssist`
- **Repository name:** `fabricassist-platform`
- **Python package namespace:** `fabricassist`
- **Expo application name:** `FabricAssist`
- **Expo slug:** `fabricassist`
- **API service name:** `fabricassist-api`
- **Worker service name:** `fabricassist-worker`
- **Frontend package/application name:** `fabricassist-app`
- **Default Docker Compose project name:** `fabricassist`
- **Environment-variable prefix for project-specific settings:** `FABRICASSIST_`

The product name must be written as **FabricAssist** in user-facing text. Lowercase `fabricassist` is reserved for repository names, package names, service identifiers, URLs, and machine-readable configuration. Do not introduce alternative product names or legacy names without an explicit branding decision.

## 2. Product goals

1. Let a user photograph or upload a garment and its care label.
2. Recognize care symbols, fibre composition, and written instructions.
3. Explain whether domestic washing, professional dry cleaning, professional wet cleaning, bleaching, tumble drying, natural drying, and ironing are permitted.
4. Recommend an appropriate detergent only when the label and material rules permit domestic washing.
5. Return the answer in the user's selected language, initially Spanish and English.
6. Reuse previously validated results to reduce latency and LLM token consumption.
7. Detect uncertain or contradictory labels and request another photo or human review instead of guessing.
8. Preserve an auditable record of the source image, extraction, model invocation, rules version, and final answer.
9. Remain deployable with open technologies locally and avoid unnecessary vendor lock-in in production.

## 3. Non-goals for the MVP

The MVP will not:

- Guarantee stain removal or fabric restoration.
- Identify unknown chemicals or recommend professional solvents for consumer use.
- Replace the judgement of a trained textile-care professional.
- Train or fine-tune a custom vision model.
- Provide automatic pricing, pickup logistics, payments, or delivery routing.
- Reproduce protected official care-symbol artwork unless the required rights have been confirmed.
- Use an autonomous multi-agent system for decisions that can be implemented deterministically.
- Require Engram, a dedicated vector database, Kubernetes, or a proprietary agent-memory service.

## 4. Users and roles

### 4.1 Customer

A customer can:

- Register, sign in, and manage their account.
- Capture or upload garment and label images.
- Request analysis.
- View processing status and results.
- Review previous scans.
- Submit feedback or request human review.
- Delete scans and associated images according to the retention policy.

### 4.2 Cleaning operator

An operator can:

- View cases requiring review.
- Inspect images, extracted facts, confidence, and proposed result.
- Correct detected symbols, composition, or written instructions.
- Approve a final result.
- Add a short customer-facing note.

### 4.3 Tenant administrator

An administrator can:

- Manage operators.
- Configure supported languages and retention settings.
- View usage and model-cost summaries.
- Activate a care-rules version.
- View audit events.

The MVP may run for one cleaning company, but the schema must include `tenant_id` on business records so that future multi-tenancy does not require a destructive migration.

## 5. Core user journeys

### 5.1 Label-led analysis

1. The user selects a preferred answer language.
2. The user captures or uploads a care-label image.
3. The application checks image quality before upload or analysis.
4. The backend searches exact-image and prior-extraction caches.
5. If no safe reusable result exists, the vision provider extracts structured facts.
6. The rules engine validates and converts the facts into a canonical care result.
7. The application renders the result in the selected language.
8. The user sees instructions, warnings, confidence, and the distinction between label facts and recommendations.

### 5.2 Garment-only analysis

1. The user captures or uploads a garment image without a readable label.
2. The system may estimate garment category, visible construction, and possible materials.
3. The result must be explicitly marked provisional.
4. The system must not claim that washing or dry cleaning is permitted solely from garment appearance.
5. The user is asked to upload the care label for a definitive answer.

### 5.3 Low-confidence flow

1. The system identifies blur, glare, crop, hidden symbols, or low model confidence.
2. The system explains how to retake the image.
3. If the user cannot provide a better image, the scan can be submitted to the operator review queue.

### 5.4 Reused answer flow

1. A safe exact or canonical match is found.
2. The previous normalized result is reused without another vision call when allowed by the cache policy.
3. The result records the cache source, original validation status, rules version, and reuse count.

## 6. Functional requirements

### 6.1 Authentication and authorization

- **FR-AUTH-001:** The API must support email/password registration and login for the MVP.
- **FR-AUTH-002:** Passwords must be hashed with Argon2id.
- **FR-AUTH-003:** Access tokens must be short-lived and refresh tokens must use rotation and revocation.
- **FR-AUTH-004:** Web refresh credentials must use `Secure`, `HttpOnly`, and appropriate `SameSite` cookies.
- **FR-AUTH-005:** Native applications must store refresh credentials using the platform secure store.
- **FR-AUTH-006:** Authorization must enforce customer, operator, and administrator roles.
- **FR-AUTH-007:** The authentication layer must be replaceable by an OpenID Connect provider later.

### 6.2 Image capture and upload

- **FR-IMG-001:** The Expo application must support camera capture and image-library selection on Android and iOS.
- **FR-IMG-002:** The web application must support file selection, drag-and-drop, and browser camera capture when available.
- **FR-IMG-003:** Images must upload directly to object storage using short-lived presigned URLs.
- **FR-IMG-004:** The API must validate allowed MIME types, declared size, actual size, and image decodability.
- **FR-IMG-005:** The default maximum upload size must be configurable; the MVP default is 12 MB per image.
- **FR-IMG-006:** The frontend should offer crop, rotate, and retake actions.
- **FR-IMG-007:** The processing service must create a normalized derivative used for hashing and model input while retaining the original according to policy.
- **FR-IMG-008:** The system must reject unsupported files and decompression-bomb-like images.

### 6.3 Image-quality checks

- **FR-QUALITY-001:** The system must calculate basic image-quality signals, including resolution, blur, brightness, and probable glare.
- **FR-QUALITY-002:** A clearly unusable image must be rejected before a paid model call.
- **FR-QUALITY-003:** The response must provide actionable capture guidance such as “move closer,” “flatten the label,” or “avoid flash reflection.”
- **FR-QUALITY-004:** Quality thresholds must be configurable and covered by tests using fixture images.

### 6.4 Scan lifecycle

A scan status must use a controlled enum with at least:

- `draft`
- `uploading`
- `queued`
- `processing`
- `needs_better_image`
- `needs_review`
- `completed`
- `failed`
- `deleted`

Requirements:

- **FR-SCAN-001:** Creating a scan must return its ID and presigned upload instructions.
- **FR-SCAN-002:** Analysis must run asynchronously.
- **FR-SCAN-003:** The client must be able to poll status and progress.
- **FR-SCAN-004:** Jobs must be idempotent and safe to retry.
- **FR-SCAN-005:** A failed model or infrastructure call must not leave the scan permanently locked.
- **FR-SCAN-006:** Users must not access scans owned by another user or tenant.

### 6.5 Vision extraction

- **FR-AI-001:** Vision providers must be accessed through a provider-neutral Python interface.
- **FR-AI-002:** The initial provider must be selected through configuration, not hard-coded in domain logic.
- **FR-AI-003:** The provider must return data validated against a strict Pydantic schema.
- **FR-AI-004:** The extraction model must not generate the final customer answer.
- **FR-AI-005:** The extraction must preserve visible written text in its original language.
- **FR-AI-006:** The extraction must normalize recognized meanings into language-independent care codes.
- **FR-AI-007:** Every material fact and care symbol must include a confidence value or explicit `unknown` state.
- **FR-AI-008:** The model must not infer a missing symbol merely because it is common for a detected material.
- **FR-AI-009:** The system must store provider, model identifier, prompt version, schema version, latency, token usage when available, and estimated cost.
- **FR-AI-010:** The implementation must support an OpenAI-compatible endpoint so a local or alternative model can be evaluated later.

The normalized schema must cover at least:

- Image type: garment, care label, both, unrelated, unusable.
- Garment category.
- Material composition and percentages.
- Washing permission, maximum temperature, and process severity.
- Bleaching permission and allowed bleach type when identifiable.
- Tumble-drying permission and heat level.
- Natural-drying instructions when identifiable.
- Ironing permission, maximum temperature, and steam restriction.
- Professional dry-cleaning permission, process letter, and severity.
- Professional wet-cleaning permission and severity.
- Written warnings.
- Overall confidence.
- Uncertain fields.

### 6.6 Deterministic care-rules engine

- **FR-RULE-001:** Final care decisions must be generated from normalized extraction data by deterministic Python code.
- **FR-RULE-002:** Rules must be versioned and immutable after activation.
- **FR-RULE-003:** The label must override material-based recommendations.
- **FR-RULE-004:** A prohibition must override a generic recommendation.
- **FR-RULE-005:** Contradictory facts must produce `needs_review`, not a guessed answer.
- **FR-RULE-006:** Professional process letters and solvents must be described as instructions for a professional cleaner, not as a domestic chemical recipe.
- **FR-RULE-007:** The rules result must separate:
  - detected label facts;
  - deterministic interpretations;
  - optional recommendations;
  - prohibited actions;
  - professional-only instructions;
  - unresolved uncertainties.
- **FR-RULE-008:** Every completed result must reference a `rules_version`.

### 6.7 Detergent recommendations

- **FR-DET-001:** Detergent advice must be generated by a separate versioned ruleset.
- **FR-DET-002:** No detergent may be recommended when washing in water is prohibited.
- **FR-DET-003:** Recommendations must use categories rather than mandatory brands in the MVP.
- **FR-DET-004:** The initial categories must cover standard colour detergent, whites detergent, delicates detergent, wool detergent, silk detergent, technical-garment wash, and no domestic detergent.
- **FR-DET-005:** Fabric softener and bleach warnings must be included when relevant.
- **FR-DET-006:** Material inference from a garment-only photo must not authorize a detergent recommendation.

### 6.8 Language and rendering

- **FR-I18N-001:** Spanish and English must be supported in the MVP.
- **FR-I18N-002:** The original user description and original label text must not be translated before extraction.
- **FR-I18N-003:** Internal care decisions must use language-independent codes and typed values.
- **FR-I18N-004:** Common answers must be rendered through maintained translation templates without an LLM call.
- **FR-I18N-005:** An LLM may be used for unusual free-text warnings only after deterministic facts have been established.
- **FR-I18N-006:** A generated explanation must never alter a prohibition or numeric temperature from the canonical result.
- **FR-I18N-007:** Rendered answers must be cached by canonical result, rules version, template version, and language.

### 6.9 Caching and token control

The application must use several cache layers:

1. Exact normalized-image SHA-256.
2. Perceptual hash for near-duplicate candidate discovery.
3. Canonical care signature.
4. Optional embedding similarity through pgvector.
5. Rendered-language answer cache.

Requirements:

- **FR-CACHE-001:** Exact image matches may reuse a validated extraction when model/schema compatibility rules allow it.
- **FR-CACHE-002:** Perceptual matches are candidates only and must pass additional checks.
- **FR-CACHE-003:** The canonical signature must include all safety-relevant symbols, composition, relevant written warnings, extraction schema version, and rules version.
- **FR-CACHE-004:** A semantic match must never override conflicting prohibitions, temperatures, or professional-care codes.
- **FR-CACHE-005:** Cache entries must record origin, validation state, hit count, creation time, and invalidation reason.
- **FR-CACHE-006:** Human-corrected results must be distinguishable from model-only results.
- **FR-CACHE-007:** Engram is not required for the MVP; PostgreSQL, pgvector, and Valkey are the authoritative memory and cache layers.

### 6.10 Human review and feedback

- **FR-REVIEW-001:** Scans with low confidence, contradictions, or sensitive material categories must enter a review queue.
- **FR-REVIEW-002:** Operators must be able to edit normalized fields and approve a result.
- **FR-REVIEW-003:** Corrections must preserve the original extraction and create an audit event.
- **FR-REVIEW-004:** Approved corrections may create or update a validated canonical cache entry.
- **FR-REVIEW-005:** Customer feedback must support at least `helpful`, `incorrect`, and `request_review`.
- **FR-REVIEW-006:** Feedback must not directly change a validated rules result without operator approval.

### 6.11 History and deletion

- **FR-HIST-001:** Customers must see their scans ordered by creation date.
- **FR-HIST-002:** A scan detail page must show current status, images when retained, final answer, and review state.
- **FR-HIST-003:** Users must be able to delete a scan.
- **FR-HIST-004:** Deletion must remove or schedule removal of object-storage files and personal associations.
- **FR-HIST-005:** Derived anonymized metrics may be retained only according to documented tenant policy.

### 6.12 Administration and audit

- **FR-ADMIN-001:** Administrators must view scan counts, cache-hit rate, review rate, model latency, model failures, and estimated model cost.
- **FR-ADMIN-002:** Rules and translation templates must expose versions in diagnostics.
- **FR-ADMIN-003:** Audit events must record security-sensitive and result-changing actions.
- **FR-ADMIN-004:** Secrets and raw refresh tokens must never appear in audit logs.

## 7. API requirements

- The API must be REST/JSON over HTTPS.
- FastAPI must expose an OpenAPI document.
- The frontend API client and TypeScript types should be generated from OpenAPI.
- API routes must be versioned under `/api/v1`.
- All mutation endpoints must support idempotency where duplicate client submission is plausible.
- Errors must use a stable machine-readable structure.
- Pagination must be cursor-based for histories and review queues.
- Dates must use ISO 8601 UTC values.
- Domain enums must be represented as stable strings.

Minimum endpoints:

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

POST   /api/v1/scans
POST   /api/v1/scans/{scan_id}/uploads/complete
POST   /api/v1/scans/{scan_id}/analyse
GET    /api/v1/scans/{scan_id}
GET    /api/v1/scans/{scan_id}/result
GET    /api/v1/scans
DELETE /api/v1/scans/{scan_id}
POST   /api/v1/scans/{scan_id}/feedback

GET    /api/v1/reviews
GET    /api/v1/reviews/{review_id}
PATCH  /api/v1/reviews/{review_id}
POST   /api/v1/reviews/{review_id}/approve

GET    /api/v1/health/live
GET    /api/v1/health/ready
GET    /api/v1/metrics
```

## 8. Frontend requirements

### 8.1 Framework

- Expo and React Native with TypeScript.
- Expo Router for universal routing.
- React Native Web for the authenticated web application.
- Use an Expo development build for normal development; do not treat Expo Go as the production runtime.

### 8.2 Libraries

Preferred baseline:

- TanStack Query for server state.
- React Hook Form and Zod for forms.
- Zustand only for small client-only state that does not belong in routing or server state.
- i18next or an equivalent typed translation layer.
- Generated OpenAPI client for API communication.

### 8.3 UX requirements

- The primary flow must be usable with one hand on a mobile device.
- Camera guidance must be visual and concise.
- The result must show the most important prohibitions first.
- The interface must clearly distinguish “detected on label” from “recommended by the system.”
- Confidence should be described in user-friendly terms; raw probability may be available in an operator view.
- Web layouts must adapt to desktop widths without duplicating business logic.
- Platform-specific files may be used for camera, drag-and-drop, secure token storage, and native notifications.

### 8.4 Accessibility

- Target WCAG 2.2 AA for web-relevant flows.
- All interactive controls require accessible labels.
- Result meaning must not depend on colour alone.
- Text must support dynamic sizing on mobile.
- Care instructions must be readable by screen readers.

## 9. Data requirements

PostgreSQL is the system of record. JSONB is permitted for evolving model payloads, but frequently queried and safety-relevant fields must also be normalized into typed columns or child tables.

Minimum entities:

- tenants
- users
- refresh_sessions
- scans
- scan_images
- image_fingerprints
- model_runs
- label_extractions
- extracted_materials
- extracted_care_facts
- care_results
- rendered_answers
- review_cases
- feedback
- ruleset_versions
- audit_events

All primary identifiers must be UUIDs. All tenant-owned records must include `tenant_id`. Database migrations must use Alembic.

## 10. Open-technology requirements

The local platform must use open-source components:

- Python and FastAPI.
- PostgreSQL.
- pgvector.
- Valkey.
- S3-compatible object storage, with MinIO acceptable for local development.
- Docker Compose.
- OpenTelemetry-compatible instrumentation.

Managed production equivalents may be used when they preserve standard protocols and data portability. Application code must not depend directly on AWS-specific SDK semantics outside infrastructure and storage adapters.

## 11. Security and privacy requirements

- All production traffic must use TLS.
- Images must be private by default.
- Presigned URLs must be short-lived and limited to one object/key and expected content constraints.
- Object keys must be generated by the server and must not use user-supplied paths.
- PostgreSQL and object storage must use encryption at rest in production.
- Secrets must come from environment injection or a secret manager, never the repository.
- Logs must not include raw image data, passwords, tokens, or full presigned URLs.
- Uploads must be validated before model submission.
- Rate limits must exist for authentication, scan creation, and analysis calls.
- Dependency and container-image vulnerability scanning must run in CI.
- Original-image retention must be configurable. The MVP default is 30 days, while structured results remain until user deletion or tenant policy expiration.
- A user deletion operation must be traceable and eventually consistent across database and object storage.
- Model-provider data-retention settings must be reviewed before production use.

## 12. Non-functional requirements

### 12.1 Performance

- API health and normal metadata requests: p95 below 500 ms under expected MVP load.
- Scan creation and presigned URL generation: p95 below 1 second.
- Cache-hit completed result: p95 below 2 seconds, excluding client upload time.
- New model analysis: target p95 below 30 seconds; processing remains asynchronous regardless of target.
- The API must not hold an HTTP request open for the full model workflow.

### 12.2 Reliability

- Jobs must use bounded retries with exponential backoff and dead-letter or failed-job visibility.
- Each stage must be idempotent.
- The database must remain authoritative for scan state.
- Valkey loss may delay work or clear transient caches but must not lose completed business records.
- Object-storage failures must produce a recoverable status.

### 12.3 Scalability

- API and worker processes must scale independently.
- Model calls must use per-tenant and global concurrency limits.
- Cache keys must be namespaced and versioned.
- Initial vector search must remain in PostgreSQL through pgvector.
- Kubernetes is not required for the MVP; containers must remain portable to it later.

### 12.4 Observability

- Emit structured JSON logs.
- Propagate a correlation ID from API request through job execution and model call.
- Export OpenTelemetry traces and metrics.
- Record queue depth, job duration, cache hit/miss, model errors, review rate, token use, and estimated cost.
- Health checks must distinguish liveness and readiness.

### 12.5 Quality

Backend gates:

- Ruff formatting and linting.
- Static type checking in strict-enough mode.
- Pytest unit and integration tests.
- Alembic migration validation.

Frontend gates:

- TypeScript strict mode.
- ESLint and formatting checks.
- Unit/component tests.
- Web end-to-end tests for the critical flow.

Domain gates:

- Every care-rule branch must be covered by table-driven tests.
- A regression fixture set must cover representative labels, low-quality images, contradictions, and prohibited treatments.
- No model change may be promoted without evaluation against the fixture set.

## 13. MVP acceptance criteria

The MVP is accepted when all of the following are demonstrable locally with Docker Compose:

1. A user can register and sign in from Expo web and at least one native platform.
2. A user can create a scan and upload a label image through a presigned URL.
3. The scan is processed asynchronously by a Python worker.
4. A configured vision provider returns a schema-validated extraction.
5. The deterministic rules engine produces a result in Spanish and English.
6. A repeated exact image is served without another paid model call.
7. An equivalent canonical care signature reuses the validated care result.
8. A low-confidence extraction enters `needs_better_image` or `needs_review`.
9. An operator can correct and approve a review case.
10. The approved result is visible to the customer and is auditable.
11. Users can view and delete their scan history.
12. Tests, linting, type checking, migrations, and Docker startup pass in CI.
13. No proprietary database, cache, queue, or vector-store dependency is required for local operation.

## 14. Delivery phases

### Phase 0 — Foundation

- Monorepo and development conventions.
- Docker Compose services.
- FastAPI skeleton, PostgreSQL migrations, Valkey connectivity, object-storage adapter.
- Expo skeleton and generated API client pipeline.
- CI quality gates.

### Phase 1 — Vertical slice

- Authentication.
- Scan creation and upload.
- Async worker.
- One vision-provider adapter.
- Strict extraction schema.
- Basic deterministic care rules.
- Spanish and English rendering.
- Result screen.

### Phase 2 — Safety and reuse

- Image-quality validation.
- Exact and perceptual hashes.
- Canonical care-signature cache.
- Review queue and corrections.
- Cost and token accounting.
- Retention and deletion jobs.

### Phase 3 — Production readiness

- AWS or platform deployment.
- Observability dashboards and alerts.
- Load testing and concurrency controls.
- Security review.
- Backup and restore test.
- Mobile release builds.

### Phase 4 — Optional expansion

- pgvector semantic candidate retrieval.
- Additional languages.
- Stain-specific workflow.
- Cleaner booking and pricing.
- Local/open multimodal model evaluation.
- OIDC and enterprise tenancy.

## 15. Instructions for the implementation agent

1. Read `docs/requirements.md` and `docs/architecture.md` completely before changing code.
2. Implement one vertical slice at a time and keep the application runnable after each slice.
3. Do not replace the selected core technologies without recording an architecture decision and explaining the migration impact.
4. Do not put business rules in prompts, route handlers, React components, or database triggers.
5. Do not let model prose become the authoritative care result.
6. Do not add a microservice unless an existing process boundary cannot satisfy independent scaling or security needs.
7. Prefer typed interfaces, dependency injection at boundaries, and small domain modules.
8. Add tests with each feature, especially for safety-relevant rules and cache reuse.
9. Generate migrations; never modify an applied migration silently.
10. Keep cloud-specific implementation behind adapters and infrastructure code.
