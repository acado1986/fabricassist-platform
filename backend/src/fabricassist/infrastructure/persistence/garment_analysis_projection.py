"""Provider-free read projection for the typed garment-analysis feature."""

from __future__ import annotations

from fabricassist.application.storefront_queries import (
    BranchSummaryView,
    CareActionView,
    ConflictView,
    GarmentAnalysisResultView,
    GarmentIssueView,
    LabelTextView,
    MaterialView,
    StainStepView,
    VersionView,
)
from fabricassist.domain.garment_analysis.models import (
    CareAction,
    EvidenceConflict,
    FabricAssistAnalysisResult,
)


def _action(action: CareAction) -> CareActionView:
    return CareActionView(
        code=action.code,
        permission=action.permission.value,
        maximum_temperature_c=action.maximum_temperature_c,
        process=action.process,
        evidence_paths=list(action.evidence_paths),
        reason_key=action.reason_key,
        professional_only=action.professional_only,
    )


def _conflict(conflict: EvidenceConflict) -> ConflictView:
    return ConflictView(
        id=conflict.conflict_id,
        field_path=conflict.field_path,
        selected_value=(
            str(conflict.selected_value) if conflict.selected_value is not None else None
        ),
        resolution_code=conflict.resolution_code,
        explanation_key=conflict.explanation_key,
        severity=conflict.severity.value,
    )


def analysis_result_view(result: FabricAssistAnalysisResult) -> GarmentAnalysisResultView:
    """Map the strict domain result to stable UI fields without provider payloads."""
    assessment = result.assessment
    inspection = assessment.garment_inspection
    label = assessment.label_extraction
    accepted_steps = (
        {step.claim.claim_id: step for step in result.validated_stain_treatment.accepted_steps}
        if result.validated_stain_treatment
        else {}
    )
    stain_steps = (
        [
            StainStepView(
                claim_id=step.claim_id,
                status=step.status,
                text=(
                    accepted_steps[step.claim_id].claim.text
                    if step.claim_id in accepted_steps
                    else None
                ),
                action_code=(
                    accepted_steps[step.claim_id].claim.action_code
                    if step.claim_id in accepted_steps
                    else "unknown"
                ),
                violation_codes=list(step.violation_codes),
            )
            for step in result.validated_stain_treatment.steps
        ]
        if result.validated_stain_treatment
        else []
    )
    return GarmentAnalysisResultView(
        schema_version=result.schema_version,
        outcome=result.care_policy.outcome.value,
        warnings=list(result.care_policy.warnings),
        category=inspection.category if inspection else "unknown",
        subtype=inspection.subtype if inspection else None,
        colors=list(inspection.colors) if inspection else [],
        pattern=inspection.pattern if inspection else "unknown",
        features=list(inspection.features) if inspection else [],
        overall_condition=inspection.overall_condition if inspection else "unknown",
        issues=[
            GarmentIssueView(
                id=issue.issue_id,
                kind=issue.kind.value,
                severity=issue.severity.value,
                location=issue.location,
                observed_description=issue.observed_description,
                confidence=issue.confidence,
                source_image_ids=list(issue.source_image_ids),
                suspected_causes=[cause.cause for cause in issue.suspected_causes],
                confirmed_cause=issue.confirmed_cause,
                cause_state=(
                    "confirmed"
                    if issue.confirmed_cause
                    else "inferred"
                    if issue.suspected_causes
                    else "unknown"
                ),
            )
            for issue in (inspection.issues if inspection else ())
        ],
        visible_label_text=[
            LabelTextView(
                image_id=item.image_id,
                text=item.text,
                language=item.language,
                confidence=item.confidence,
            )
            for item in (label.visible_text if label else ())
        ],
        materials=[
            MaterialView(
                material=item.material,
                percentage=item.percentage,
                confidence=item.confidence,
                source_image_ids=list(item.source_image_ids),
            )
            for item in (label.materials if label else ())
        ],
        label_warnings=list(label.written_warnings) if label else [],
        allowed_actions=[_action(item) for item in result.care_policy.allowed_actions],
        prohibited_actions=[_action(item) for item in result.care_policy.prohibited_actions],
        unknown_actions=[_action(item) for item in result.care_policy.unknown_actions],
        professional_only_actions=[
            _action(item) for item in result.care_policy.professional_only_actions
        ],
        uncertainties=list(assessment.uncertainties),
        clearer_image_requests=list(result.clearer_image_requests),
        conflicts=[_conflict(item) for item in result.care_policy.conflicts],
        branches=[
            BranchSummaryView(
                branch=item.branch_name,
                status="completed",
                schema_version=item.schema_version,
            )
            for item in assessment.branch_references
        ],
        stain_steps=stain_steps,
        history_event_ids=list(result.recommendation.history_event_ids),
        preference_source=result.recommendation.preference_source,
        versions=[VersionView(name=name, value=value) for name, value in result.versions.items()],
        product_barcode=assessment.product_barcode,
        product_lookup_status=assessment.product_lookup_status,
        product_source=assessment.product_source,
        product_facts=(
            assessment.product_facts.model_dump(mode="json")
            if assessment.product_facts is not None
            else None
        ),
    )
