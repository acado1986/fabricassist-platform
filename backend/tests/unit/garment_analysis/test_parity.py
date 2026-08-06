from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabricassist.application.garment_analysis import render_v2_answer
from fabricassist.domain.garment_analysis.models import (
    CarePolicy,
    CareRecommendation,
    FabricAssistAnalysisResult,
    MergedGarmentAssessment,
    ValidationOutcome,
)
from fabricassist.domain.garment_analysis.parity import (
    BarcodeCandidateStatus,
    BarcodeCandidateValue,
    BarcodeDecoder,
    ExecutionSnapshot,
)


def test_parity_contracts_reject_untrusted_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BarcodeCandidateValue(
            image_id=uuid4(),
            raw_value="4006381333931",
            status=BarcodeCandidateStatus.VALID,
            decoder=BarcodeDecoder.LOCAL,
            provider_payload="do-not-accept",  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        ExecutionSnapshot(
            module_version="module",
            workflow_version="workflow",
            provider="mock",
            model="model",
            prompt_versions={},
            schema_versions={},
            preprocessing_version="normalization",
            branch_routing_version="routing",
            cache_version="cache",
            product_adapter_version="product",
            identity_policy_version="identity",
            care_policy_version="care",
            rendering_version="rendering",
            unexpected_flag=True,  # type: ignore[call-arg]
        )


def test_v2_renderer_is_provider_free_and_localized() -> None:
    result = FabricAssistAnalysisResult(
        assessment=MergedGarmentAssessment(revision_id=uuid4()),
        care_policy=CarePolicy(
            care_policy_version="care-policy-v2",
            policy_checksum="checksum",
            outcome=ValidationOutcome.NEEDS_REVIEW,
        ),
        recommendation=CareRecommendation(
            recommendation_id=uuid4(),
            preference_source="none",
        ),
    )
    english = render_v2_answer(
        result_id=uuid4(), result=result, language="en", template_version="care-rendering-v2"
    )
    spanish = render_v2_answer(
        result_id=uuid4(), result=result, language="es", template_version="care-rendering-v2"
    )
    assert english.sections["validation_state"] == "A care specialist needs to review this"
    assert spanish.sections["validation_state"] == "Un especialista debe revisar este caso"
    assert english.provenance == ()
