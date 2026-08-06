from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import ValidationError

from fabricassist.api.routes.scans import ImageRequest
from fabricassist.domain.evidence import ImageRole
from fabricassist.domain.garment_analysis.image_routing import (
    AnalysisImage,
    ImageViewpoint,
    LabelScope,
    QualityState,
)
from fabricassist.infrastructure.garment_analysis.images import (
    ImageQualityThresholds,
    assess_image_quality,
)


def image_bytes(*, size: tuple[int, int], color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


def test_quality_adapter_rejects_minimum_resolution_before_provider_calls() -> None:
    assessment = assess_image_quality(image_bytes(size=(319, 500), color="white"))

    assert assessment.state == QualityState.UNUSABLE.value
    assert 0 <= assessment.glare_score <= 1
    assert assessment.orientation_degrees == 0


def test_quality_adapter_marks_uniform_large_input_borderline_not_usable() -> None:
    assessment = assess_image_quality(image_bytes(size=(500, 500), color="white"))

    assert assessment.state == QualityState.BORDERLINE.value
    assert assessment.crop_readability_score < 0.05


def test_quality_thresholds_are_configurable_for_fixture_policy_tests() -> None:
    assessment = assess_image_quality(
        image_bytes(size=(500, 500), color="white"),
        ImageQualityThresholds(maximum_brightness=1.0, borderline_glare=1.1),
    )

    assert assessment.state == QualityState.BORDERLINE.value


def test_image_metadata_rejects_viewpoint_for_label_images() -> None:
    with pytest.raises(ValidationError, match="viewpoint"):
        AnalysisImage(
            image_id=uuid4(),
            role=ImageRole.CARE_LABEL,
            viewpoint=ImageViewpoint.FRONT,
            display_order=0,
        )


def test_upload_request_rejects_metadata_that_cannot_route_to_the_declared_role() -> None:
    with pytest.raises(ValidationError, match="label_scope"):
        ImageRequest(
            role=ImageRole.DAMAGE_CLOSEUP,
            content_type="image/jpeg",
            label_scope=LabelScope.COMBINED,
        )


def test_image_metadata_accepts_combined_label_scope() -> None:
    image = AnalysisImage(
        image_id=uuid4(),
        role=ImageRole.CARE_LABEL,
        label_scope=LabelScope.COMBINED,
        quality_state=QualityState.BORDERLINE,
        display_order=0,
    )

    assert image.label_scope is LabelScope.COMBINED
    assert image.quality_state is QualityState.BORDERLINE
