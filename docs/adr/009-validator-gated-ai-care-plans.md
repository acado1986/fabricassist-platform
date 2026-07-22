# ADR-009: Use validator-gated AI care plans

- **Status:** Accepted
- **Date:** 2026-07-22
- **Supersedes:** [ADR-005](005-deterministic-care-rules.md)

## Context

The initial architecture limited the model to evidence extraction and required
deterministic rules to construct a small final care result. FabricAssist now
needs richer multi-photo reasoning about garment construction, materials,
visible stains, condition, preparation, cleaning, drying, ironing, prohibited
actions, professional care, and follow-up questions. Encoding every useful
recommendation as a deterministic decision tree would make the domain rigid and
would not support useful contextual conversation.

Arbitrary model prose still cannot be trusted to respect care-label
prohibitions, temperatures, professional-only processes, uncertainty, or
consumer chemical-safety boundaries.

## Decision

FabricAssist separates three versioned artifacts:

1. a strict structured evidence dossier with provenance and confidence;
2. a strict structured AI-proposed care plan; and
3. a deterministic Python validation report.

The active validator may accept, accept with warnings, block, request a better
image, or require human review. It does not silently invent a different care
plan. One constrained retry may provide machine-readable violations to the
planner; a second failure is not released as approved guidance.

Only a plan that passes the active immutable validation-policy version may be
presented as actionable. Free-form prose is explanatory and may not introduce
an actionable claim absent from the validated structured plan. Safety-relevant
chat claims use the same gate.

Evidence authority remains:

```text
explicit photographed care-label instruction
    > photographed normalized care symbol
    > exact verified manufacturer data for the matching variant
    > verified product-catalog data
    > material-specific recommendation
    > generic advice
```

Photographed prohibitions always win. Garment-only evidence remains provisional,
professional solvents are never turned into consumer recipes, and visual stain
identity remains a hypothesis unless confirmed by the user or verified evidence.

## Consequences

- Extraction, proposal, validator, rendering, and chat contracts require
  independent schema and version metadata.
- Existing `care.py` result generation must be migrated into domain evidence,
  proposal, and validation modules without reversing the application-to-domain
  dependency direction.
- Validation policies and activated checksums remain immutable and require
  table-driven safety regression tests and textile-care review.
- Results must persist the proposal and validation report separately for audit.
- Rich natural-language explanations are allowed only alongside the validated
  structured plan and source-aware uncertainty.
- This is a breaking cutover: remove the old `decide_care()` execution and
  narrow result/render contracts rather than keeping compatibility shims or
  dual paths. Applied Alembic revisions remain immutable; a new migration may
  transform retained rows into the new representation and then remove obsolete
  legacy structures.
