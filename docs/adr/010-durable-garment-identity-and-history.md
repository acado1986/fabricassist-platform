# ADR-010: Separate physical garment identity from product identity

- **Status:** Accepted
- **Date:** 2026-07-22

## Context

FabricAssist must recognize garments handled before, reuse verified stable
evidence, analyze only new observations where safe, preserve cleaning history,
and show users what changed. Retail barcodes, brand, and model normally identify
a product line or variant rather than one physical item. Visual similarity can
also confuse identical garments owned by different customers.

## Decision

Persist a tenant/user-owned physical `garment` separately from a reusable
`product_profile`. A garment has identifiers, evidence revisions, observations,
conversation threads, and append-only service events.

Identity resolution returns one of:

- `exact_instance` — a FabricAssist QR/serial or other verified instance ID;
- `probable_instance` — a strong tenant/user-scoped composite match requiring
  confirmation;
- `same_product` — product/variant match only, never physical-history proof;
- `visual_candidate` — pHash/visual candidate requiring confirmation;
- `new_garment`; or
- `identity_conflict`.

Product-level, probable, and visual candidates never automatically receive a
physical garment's stains, damage, conversation, or service history. Cross-user
physical-garment matching is prohibited. FabricAssist distinguishes
`analysed_before` from `cleaned_before`; only a confirmed performed-service event
may claim cleaning occurred.

New photos create an analysis revision and immutable/superseding observations.
The worker may extract only new images, but the merged dossier and complete care
plan are always revalidated before activation.

## Consequences

- New garment, product, identifier, revision, observation, and service-event
  tables and indexes require Alembic migrations.
- One extraction/result per scan constraints must be replaced by revision-aware
  relationships and an active revision/result pointer.
- The client needs candidate confirmation, analysed/cleaned history, change
  summaries, and an optional FabricAssist QR-tag flow.
- Exact identifiers are implemented before embeddings; vector/visual retrieval
  remains candidate discovery only.
- Deletion and retention must cover garment associations, images, conversations,
  lookup provenance, and service history according to policy.
