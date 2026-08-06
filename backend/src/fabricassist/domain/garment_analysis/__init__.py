"""Pure, provider- and persistence-independent garment-analysis v2 domain."""

from fabricassist.domain.garment_analysis.care_policy import (
    CarePolicyRegistry,
    derive_safety_envelope,
    resolve_practical_preference,
    validate_candidate_claims,
)
from fabricassist.domain.garment_analysis.evidence_merge import EvidenceMerger
from fabricassist.domain.garment_analysis.image_routing import (
    ImageQualitySignals,
    ImageViewpoint,
    LabelScope,
    QualityState,
    route_images,
)
from fabricassist.domain.garment_analysis.models import *  # noqa: F403
from fabricassist.domain.garment_analysis.stain_policy import (
    is_stain_analysis_eligible,
    validate_stain_treatment,
)

__all__ = [
    "CarePolicyRegistry",
    "EvidenceMerger",
    "ImageQualitySignals",
    "ImageViewpoint",
    "LabelScope",
    "QualityState",
    "derive_safety_envelope",
    "is_stain_analysis_eligible",
    "resolve_practical_preference",
    "route_images",
    "validate_candidate_claims",
    "validate_stain_treatment",
]
