from uuid import uuid4

from fabricassist.domain.evidence import ImageRole
from fabricassist.domain.garment_analysis.evidence_merge import EvidenceMerger
from fabricassist.domain.garment_analysis.image_routing import (
    AnalysisImage,
    QualityState,
    route_images,
)
from fabricassist.domain.garment_analysis.models import (
    EvidenceCertainty,
    EvidenceSourceKind,
    FactCandidate,
    FieldEvidence,
    MergedGarmentAssessment,
)


def candidate(
    field: str, value: str, kind: EvidenceSourceKind, *, written: bool = False
) -> FactCandidate:
    return FactCandidate(
        field_path=field,
        value=value,
        explicit_written_instruction=written,
        evidence=FieldEvidence(
            field_path=field,
            source_kind=kind,
            source_image_ids=(uuid4(),),
            certainty=EvidenceCertainty.OBSERVED,
            confidence=60,
        ),
    )


def test_image_router_excludes_unusable_labels_and_unknown_other() -> None:
    overview, stain, label, barcode, unusable, other = (uuid4() for _ in range(6))
    routed = route_images(
        (
            AnalysisImage(image_id=overview, role=ImageRole.GARMENT_OVERVIEW, display_order=0),
            AnalysisImage(image_id=stain, role=ImageRole.STAIN_CLOSEUP, display_order=1),
            AnalysisImage(image_id=label, role=ImageRole.CARE_LABEL, display_order=2),
            AnalysisImage(image_id=barcode, role=ImageRole.BARCODE_BRAND_LABEL, display_order=3),
            AnalysisImage(
                image_id=unusable,
                role=ImageRole.COMPOSITION_LABEL,
                quality_state=QualityState.UNUSABLE,
                display_order=4,
            ),
            AnalysisImage(image_id=other, role=ImageRole.OTHER, display_order=5),
        )
    )
    assert routed.garment_inspection == (overview, stain)
    assert routed.label_extraction == (label,)
    assert routed.barcode_enrichment == (barcode,)
    assert routed.stain_treatment == (stain, overview)
    assert set(routed.excluded) == {unusable, other}


def test_merger_preserves_conflict_and_prefers_photographed_prohibition() -> None:
    label_prohibition = candidate(
        "care.wash.permission", "prohibited", EvidenceSourceKind.PHOTOGRAPHED_LABEL, written=True
    )
    catalog_permission = candidate(
        "care.wash.permission", "allowed", EvidenceSourceKind.VERIFIED_LOOKUP
    )
    assessment = MergedGarmentAssessment(
        revision_id=uuid4(), source_observations=(catalog_permission, label_prohibition)
    )

    merged = EvidenceMerger().merge(assessment)

    assert merged.selected_facts[0].value == "prohibited"
    assert merged.conflicts[0].resolution_code == "SAFETY_AUTHORITY"
    assert "conflict:care.wash.permission" in merged.uncertainties


def test_merger_keeps_photographed_composition_over_visual_inference() -> None:
    visual = candidate("composition.primary", "wool", EvidenceSourceKind.VISUAL_INFERENCE)
    label = candidate("composition.primary", "acrylic", EvidenceSourceKind.PHOTOGRAPHED_LABEL)
    merged = EvidenceMerger().merge(
        MergedGarmentAssessment(revision_id=uuid4(), source_observations=(visual, label))
    )
    assert merged.selected_facts[0].value == "acrylic"
    assert merged.conflicts[0].resolution_code == "FACTUAL_AUTHORITY"
