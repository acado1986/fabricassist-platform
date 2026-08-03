"""Pure deterministic assembly of the v2 merged assessment and care result."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from pydantic import JsonValue

from fabricassist.domain.garment_analysis.care_policy import (
    CARE_POLICY_VERSION,
    derive_safety_envelope,
    resolve_practical_preference,
)
from fabricassist.domain.garment_analysis.cleaning_history import GarmentServiceEvent
from fabricassist.domain.garment_analysis.evidence_merge import EvidenceMerger
from fabricassist.domain.garment_analysis.models import (
    BranchReference,
    CareRecommendation,
    EvidenceCertainty,
    EvidenceCorrection,
    EvidenceSourceKind,
    FabricAssistAnalysisResult,
    FactCandidate,
    FieldEvidence,
    GarmentInspection,
    LabelExtraction,
    MergedGarmentAssessment,
    Permission,
    ValidationOutcome,
)


def _candidate(
    *,
    field_path: str,
    value: JsonValue,
    evidence: FieldEvidence,
    explicit_written_instruction: bool = False,
) -> FactCandidate:
    return FactCandidate(
        field_path=field_path,
        value=value,
        evidence=evidence,
        explicit_written_instruction=explicit_written_instruction,
    )


def _instruction_candidates(label: LabelExtraction | None) -> tuple[FactCandidate, ...]:
    if label is None:
        return ()
    candidates: list[FactCandidate] = []
    instructions = (
        ("care.wash.permission", label.wash),
        ("care.bleach.permission", label.bleach),
        ("care.tumble_dry.permission", label.tumble_dry),
        ("care.natural_drying.permission", label.natural_drying),
        ("care.iron.permission", label.ironing),
        ("care.dry_clean.permission", label.dry_clean),
        ("care.professional_wet_clean.permission", label.professional_wet_clean),
    )
    for field_path, instruction in instructions:
        if instruction is not None:
            candidates.append(
                _candidate(
                    field_path=field_path,
                    value=instruction.permission.value,
                    evidence=instruction.evidence,
                    explicit_written_instruction=bool(instruction.evidence.original_text),
                )
            )
    if label.wash is not None and label.wash.maximum_temperature_c is not None:
        candidates.append(
            _candidate(
                field_path="care.wash.maximum_temperature_c",
                value=label.wash.maximum_temperature_c,
                evidence=label.wash.evidence,
            )
        )
    if label.ironing is not None and label.ironing.maximum_temperature_c is not None:
        candidates.append(
            _candidate(
                field_path="care.iron.maximum_temperature_c",
                value=label.ironing.maximum_temperature_c,
                evidence=label.ironing.evidence,
            )
        )
    return tuple(candidates)


def _history_candidates(events: Iterable[GarmentServiceEvent]) -> tuple[FactCandidate, ...]:
    candidates: list[FactCandidate] = []
    for event in events:
        evidence = FieldEvidence(
            field_path="care.history",
            source_kind=EvidenceSourceKind.CLEANING_HISTORY,
            certainty=EvidenceCertainty.CONFIRMED,
            confidence=90 if event.exact_garment_confirmed else 0,
            uncertainty_reason=None,
        )
        if event.water_temperature_c is not None:
            candidates.append(
                _candidate(
                    field_path="care.wash.maximum_temperature_c",
                    value=event.water_temperature_c,
                    evidence=evidence.model_copy(
                        update={"field_path": "care.wash.maximum_temperature_c"}
                    ),
                )
            )
        if event.drying_method == "tumble_dry":
            candidates.append(
                _candidate(
                    field_path="care.tumble_dry.permission",
                    value=Permission.ALLOWED.value,
                    evidence=evidence.model_copy(
                        update={"field_path": "care.tumble_dry.permission"}
                    ),
                )
            )
    return tuple(candidates)


def _correction_candidates(
    corrections: Iterable[EvidenceCorrection],
) -> tuple[FactCandidate, ...]:
    return tuple(
        _candidate(
            field_path=correction.field_path,
            value=correction.corrected_value,
            evidence=FieldEvidence(
                field_path=correction.field_path,
                source_kind=EvidenceSourceKind.HUMAN_CORRECTION,
                source_image_ids=(correction.source_image_id,)
                if correction.source_image_id is not None
                else (),
                certainty=EvidenceCertainty.CONFIRMED,
                confidence=100,
            ),
        )
        for correction in corrections
        if correction.confirmation.value == "accepted"
    )


def finalize_analysis(
    *,
    revision_id: UUID,
    branch_references: tuple[BranchReference, ...],
    garment_inspection: GarmentInspection | None,
    label_extraction: LabelExtraction | None,
    history: tuple[GarmentServiceEvent, ...] = (),
    corrections: tuple[EvidenceCorrection, ...] = (),
    versions: dict[str, str] | None = None,
) -> FabricAssistAnalysisResult:
    """Produce a conservative v2 result without a planning-provider call.

    Historical and correction facts remain source observations; their authority
    never changes the label-derived policy envelope.
    """
    assessment = MergedGarmentAssessment(
        revision_id=revision_id,
        branch_references=branch_references,
        garment_inspection=garment_inspection,
        label_extraction=label_extraction,
        source_observations=(
            *_instruction_candidates(label_extraction),
            *_history_candidates(history),
            *_correction_candidates(corrections),
        ),
    )
    merged = EvidenceMerger().merge(assessment)
    policy = derive_safety_envelope(merged)
    recommendation: CareRecommendation = resolve_practical_preference(policy, history)
    clearer_image_requests: tuple[str, ...] = ()
    if policy.outcome is ValidationOutcome.NEEDS_BETTER_IMAGE:
        clearer_image_requests = ("care_label",)
    return FabricAssistAnalysisResult(
        assessment=merged,
        care_policy=policy,
        recommendation=recommendation,
        clearer_image_requests=clearer_image_requests,
        versions={
            "merged_assessment": merged.schema_version,
            "care_policy": CARE_POLICY_VERSION,
            "detergent_policy": "care-policy-v2",
            "rendering_template": "care-rendering-v2",
            **(versions or {}),
        },
        localization_template_inputs={
            "outcome": policy.outcome.value,
            "allowed_action_codes": [action.code for action in policy.allowed_actions],
            "prohibited_action_codes": [action.code for action in policy.prohibited_actions],
        },
    )
