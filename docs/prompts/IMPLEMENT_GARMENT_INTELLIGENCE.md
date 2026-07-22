# Codex handoff prompt — implement FabricAssist garment intelligence

Copy the prompt below into a fresh Codex session opened at the repository root.

---

You are working in:

```text
/home/bogdan/Projects/fabricassist-platform
```

## Mandatory preparation

Before changing code, read these files completely in this order:

1. `AGENTS.md`
2. `docs/requirements.md`
3. `docs/architecture.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. The nearest nested `AGENTS.md` for every file you edit, if any
6. `docs/adr/009-validator-gated-ai-care-plans.md`
7. `docs/adr/010-durable-garment-identity-and-history.md`
8. `docs/adr/011-trusted-product-information-lookup.md`
9. `docs/adr/012-server-owned-contextual-conversations.md`
10. `docs/database.md`

Inspect the existing repository, migrations, tests, OpenAPI artifacts, generated
client, and `git status` before selecting files or dependencies. Preserve user
changes. Do not commit or push unless I explicitly ask.

## Approved target architecture

FabricAssist is migrating from the narrow two-photo/extraction-only/v1
deterministic-result slice to:

```text
multiple typed photos
    -> source-referenced garment evidence dossier
    -> optional trusted barcode/product enrichment
    -> AI-proposed strict care plan
    -> deterministic versioned validation gate
    -> rich Spanish/English result
    -> durable garment identity/history
    -> contextual validator-gated chat
```

Mandatory boundaries:

- Photographed written/symbol care-label evidence remains authoritative.
- AI may propose care, but free-form prose is never the sole actionable result.
- Validators accept, warn, block, request another image, or require review; they
  do not silently invent a replacement plan.
- At most one constrained proposal retry may use machine-readable violations.
- A retail barcode/brand/model identifies a product candidate, not one physical
  garment. Only a verified instance ID or prior confirmed relationship auto-links.
- Keep `analysed_before` separate from confirmed `cleaned_before` service events.
- Incremental extraction may inspect only new images, but the complete merged
  dossier and plan must always be revalidated.
- Product data must be sourced and never override the physical label.
- Do not fetch arbitrary QR URLs; enforce explicit outbound/SSRF policy in the
  product-lookup phase.
- Conversation state belongs in PostgreSQL and every actionable chat claim uses
  the same validator.
- PostgreSQL is authoritative; Valkey remains an optimization.
- Default tests and local startup must not require a paid model or catalog.
- The cutover is intentionally not backward compatible. Remove legacy image
  roles, fixed two-photo contracts/UI, narrow result fields, compatibility
  mappers, dual writes, and fallback execution through `decide_care()` as their
  replacement phase lands.

## Execution rule

Implement one coherent release from `docs/IMPLEMENTATION_PLAN.md`, starting with
the earliest release whose acceptance criteria are not already proven. Do not
infer completion from file names alone; inspect behavior, migrations, tests,
generated contracts, and documentation.

For the current repository, the expected next slice is the coordinated breaking
core release:

## Phases 10–13 — Breaking multi-photo analysis, planning, validation, and result

Implement Phases 10–13 as one end-to-end vertical slice. They may be separated
into reviewable internal commits, but do not stop with a released partial system
that retains or falls back to the old analysis path. Do not begin Phases 14–19.

### Required behavior

1. Replace the API assumption of at most one `garment` plus one `care_label`
   image with a configurable default maximum of eight completed images.
2. Support repeated roles:
   - `garment_overview`
   - `care_label`
   - `composition_label`
   - `barcode_brand_label`
   - `stain_closeup`
   - `damage_closeup`
   - `construction_detail`
   - `other`
3. Remove the legacy fixed two-photo/image-role contract. Old clients are
   intentionally unsupported after the coordinated backend/OpenAPI/client/UI cutover.
4. Add revision-aware persistence through a **new** Alembic migration after
   current head. Never edit `20260721_0001`, `0002`, or `0003`.
5. Add the minimum physical `garments` and `analysis_revisions` foundation,
   triggering-image membership, supersession, and active revision/result pointers
   needed by later phases. Do not implement identity matching yet.
6. Add a new migration that transforms any current rows selected for retention
   into revision-owned structures, then removes obsolete one-extraction/result-
   per-scan constraints and legacy columns/tables. Do not add dual schema reads or writes.
7. Replace `POST /api/v1/scans` so it creates a draft scan without embedded
   image declarations or upload instructions. Add typed image collection operations:
   - `POST /api/v1/scans/{scan_id}/images`
   - `DELETE /api/v1/scans/{scan_id}/images/{image_id}`
   - retain current scan creation/upload-completion/analyse behavior
8. Enforce tenant/ownership authorization, upload lifecycle, server-generated
   object keys, private storage, idempotency where duplicates are plausible, and
   no presigned URL/object-key logging.
9. Replace the Expo screen's fixed two-slot state with an accessible,
   camera-first, reorderable multi-photo gallery supporting repeated roles,
   preview, replace/remove, upload fallback, limits, and per-role guidance.
10. Replace `LabelExtractionPayload` with the Phase 11 source-referenced garment
    evidence dossier and evidence-delta merge. Move domain evidence types out of
    application/provider modules and remove the reverse `domain/care.py` to
    `application/vision.py` dependency.
11. Implement Phase 12 `CarePlanningProvider`, strict `ProposedCarePlan`,
    deterministic `CareValidationReport`, versioned policy/checksum, and one
    constrained retry for explicitly repairable violations.
12. Delete `decide_care()` and the narrow v1 result/render execution. Do not add
    a compatibility mapper, legacy endpoint, dual write, or fallback renderer.
13. Implement the Phase 13 typed rich result and Spanish/English accessible UI,
    including sources, warnings, preparation, stain guidance, cleaning,
    detergent, drying, ironing, professional care, prohibitions, confidence,
    uncertainty, validation state, and change summary.
14. Do not begin product lookup, physical-garment identity matching, service
    history, caching expansion, or chat.

### Architecture and cutover requirements

- Keep domain code independent of FastAPI, SQLAlchemy, Celery, Valkey, boto3, and
  provider SDKs.
- Do not deepen the current reverse dependency from `domain/care.py` to
  `application/vision.py`; Phase 11 removes it.
- Use typed Pydantic response/request models. Replace untyped API result shapes
  only when the phase requires it.
- FastAPI OpenAPI remains the frontend contract; regenerate the committed
  OpenAPI and generated TypeScript client and never hand-edit generated files.
- Add the smallest dependency only if the selected stack/standard library cannot
  safely solve the need; Phase 10 should not require a barcode library.
- Maintain Spanish/English typed translations and accessibility.
- Add/update `.env.example`, README, database docs, and API documentation only
  for configuration/behavior introduced in this phase.

### Required tests

Add or update tests for at least:

- one image, eight images, and over-limit rejection;
- multiple images with the same role;
- every accepted role and invalid role;
- upload completion, order, remove, retry, and incomplete upload;
- wrong user and wrong tenant denial for every new operation;
- object deletion/cleanup behavior for removed images;
- idempotent duplicate image operations where applicable;
- explicit rejection/removal of legacy image roles and fixed two-photo request shapes;
- worker creation/activation of an analysis revision;
- empty database and previous-head migration to new head;
- intended downgrade behavior and model/schema drift;
- generated OpenAPI/client drift;
- Expo gallery component behavior, accessibility, translations, and web build;
- Android development-build capture/upload smoke before claiming native complete.
- multi-image source provenance and deterministic evidence-delta merge;
- every proposal/validator branch, retry-once behavior, and no second invalid release;
- photographed prohibitions, garment-only provisional state, sensitive materials,
  stain uncertainty, and professional-solvent safety;
- explicit proof that legacy `decide_care()`, old roles, old result shape, and
  fallback renderer are absent;
- rich ES/EN result invariants, source badges, accessibility, and Android result smoke.

Use synthetic/licensed image fixtures only. Do not call a paid provider in
default tests.

### Validation

Run the relevant commands actually available in the repository, including:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest backend/tests
pnpm --dir frontend format:check
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build:web
make openapi
make migration-test
make check
git diff --check
```

Use focused commands while iterating. Fix failures caused by the change. Do not
claim a command passed unless it actually completed successfully. If Android
hardware/emulator is unavailable, report that check as not run.

## Completion report

At the end, provide:

1. Concise implementation summary.
2. Important files changed.
3. Breaking migration and removed legacy behavior.
4. Environment-variable or local-start instructions.
5. Exact validation commands and results.
6. Security/privacy impact.
7. Remaining risks or deferred work.
8. The next approved release (Phase 14), but do not implement it automatically.

Do not expand beyond the coordinated Phases 10–13 core vertical slice.

---

After the Phases 10–13 cutover is accepted, reuse the preparation and boundaries
above but ask the next session to implement Phase 14 only. Continue sequentially
through Phase 19; each release must leave the repository runnable and tests passing.
