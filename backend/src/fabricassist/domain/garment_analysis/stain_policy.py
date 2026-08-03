"""Conservative eligibility and immutable validation for optional stain analysis."""

from __future__ import annotations

from fabricassist.domain.garment_analysis.care_policy import validate_candidate_claims
from fabricassist.domain.garment_analysis.models import (
    CarePolicy,
    EvidenceConflict,
    GarmentInspection,
    StainTreatment,
    ValidatedStainTreatment,
    ValidationOutcome,
)


def is_stain_analysis_eligible(
    *,
    stain_image_count: int,
    user_requested: bool,
    inspection: GarmentInspection | None,
    policy: CarePolicy,
    feature_enabled: bool,
    reusable_success_exists: bool,
) -> bool:
    if not feature_enabled or reusable_success_exists:
        return False
    if stain_image_count < 1 and not user_requested:
        return False
    has_relevant_stain = inspection is not None and any(
        issue.kind.value == "stain" and issue.source_image_ids for issue in inspection.issues
    )
    if not has_relevant_stain:
        return False
    return policy.outcome not in {
        ValidationOutcome.NEEDS_BETTER_IMAGE,
        ValidationOutcome.NEEDS_REVIEW,
    }


def validate_stain_treatment(
    policy: CarePolicy, treatment: StainTreatment
) -> ValidatedStainTreatment:
    report = validate_candidate_claims(policy, tuple(step.claim for step in treatment.steps))
    conflicts: list[EvidenceConflict] = []
    if report.blocked_claim_ids:
        # The proposal remains untouched; a future renderer uses accepted IDs only.
        conflicts.extend(policy.conflicts)
    return ValidatedStainTreatment(
        treatment_id=treatment.treatment_id,
        accepted_claim_ids=report.accepted_claim_ids,
        blocked_claim_ids=report.blocked_claim_ids,
        conflicts=tuple(conflicts),
        outcome=report.outcome,
        care_policy_version=policy.care_policy_version,
    )
