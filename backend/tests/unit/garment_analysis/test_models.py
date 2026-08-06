from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabricassist.domain.garment_analysis.models import (
    CauseHypothesis,
    CorrectionConfirmation,
    CorrectionSource,
    EvidenceCertainty,
    EvidenceCorrection,
    EvidenceSourceKind,
    FieldEvidence,
    GarmentIssue,
    GarmentIssueKind,
    IssueSeverity,
    LabelExtraction,
    MaterialComposition,
)


def photographed_evidence(field: str = "care.wash") -> FieldEvidence:
    return FieldEvidence(
        field_path=field,
        source_kind=EvidenceSourceKind.PHOTOGRAPHED_LABEL,
        source_image_ids=(uuid4(),),
        certainty=EvidenceCertainty.OBSERVED,
        confidence=98,
    )


def test_unknown_field_evidence_requires_reason_and_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="uncertainty_reason"):
        FieldEvidence(
            field_path="care.wash",
            source_kind=EvidenceSourceKind.PHOTOGRAPHED_LABEL,
            certainty=EvidenceCertainty.UNKNOWN,
            confidence=0,
        )
    with pytest.raises(ValidationError):
        FieldEvidence.model_validate({**photographed_evidence().model_dump(), "extra": "no"})


def test_visual_issue_cause_cannot_be_confirmed_from_appearance() -> None:
    with pytest.raises(ValidationError, match="confirmed cause"):
        GarmentIssue(
            issue_id=uuid4(),
            kind=GarmentIssueKind.STAIN,
            severity=IssueSeverity.MINOR,
            location="cuff",
            observed_description="small dark mark",
            confidence=80,
            source_image_ids=(uuid4(),),
            confirmed_cause="wine",
            confirmed_cause_source=EvidenceSourceKind.VISUAL_INFERENCE,
        )

    issue = GarmentIssue(
        issue_id=uuid4(),
        kind=GarmentIssueKind.STAIN,
        severity=IssueSeverity.MINOR,
        location="cuff",
        observed_description="small dark mark",
        confidence=80,
        source_image_ids=(uuid4(),),
        suspected_causes=(
            CauseHypothesis(cause="wine", confidence=30, source_image_ids=(uuid4(),)),
        ),
    )
    assert issue.confirmed_cause is None


def test_material_percentage_mismatch_is_explicit_uncertainty_not_normalized() -> None:
    label = LabelExtraction(
        materials=(
            MaterialComposition(
                material="cotton", percentage=80, confidence=99, source_image_ids=(uuid4(),)
            ),
            MaterialComposition(
                material="polyester", percentage=30, confidence=99, source_image_ids=(uuid4(),)
            ),
        ),
        overall_confidence=95,
    )
    assert label.material_percentage_uncertainty == "MATERIAL_PERCENTAGES_DO_NOT_TOTAL_100"


def test_customer_safety_correction_cannot_be_authoritative_without_review() -> None:
    with pytest.raises(ValidationError, match="require image evidence"):
        EvidenceCorrection(
            correction_id=uuid4(),
            revision_id=uuid4(),
            field_path="wash.permission",
            previous_value="prohibited",
            corrected_value="allowed",
            source=CorrectionSource.CUSTOMER,
            reason="I believe it is washable",
            confirmation=CorrectionConfirmation.ACCEPTED,
        )
