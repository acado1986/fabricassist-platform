from __future__ import annotations

from fabricassist.application.vision import LabelExtractionPayload
from fabricassist.domain.care import decide_care


def test_water_wash_prohibition_always_blocks_domestic_detergent() -> None:
    result = decide_care(
        LabelExtractionPayload(
            image_type="care_label",
            wash_permission="prohibited",
            dry_clean_permission="allowed",
            overall_confidence=95,
        )
    )

    assert result.status == "completed"
    assert result.prohibitions == ["do_not_wash_in_water"]
    assert result.detergent == "no_domestic_detergent"


def test_unknown_wash_fact_needs_review_not_a_guess() -> None:
    result = decide_care(LabelExtractionPayload(image_type="care_label", overall_confidence=95))

    assert result.status == "needs_review"
    assert result.detergent == "no_domestic_detergent"
