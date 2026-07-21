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


def test_dual_image_evidence_accepts_a_confirmed_care_label() -> None:
    result = decide_care(
        LabelExtractionPayload(
            image_type="both",
            wash_permission="allowed",
            max_wash_temperature_c=30,
            wash_process="mild",
            bleach_permission="prohibited",
            tumble_permission="prohibited",
            iron_permission="allowed",
            overall_confidence=90,
        )
    )

    assert result.status == "completed"
    assert result.actions == ["wash_in_water"]
    assert result.prohibitions == ["do_not_bleach", "do_not_tumble_dry"]
    assert result.detergent == "delicates_detergent"


def test_review_preserves_confirmed_label_facts_for_an_opt_in_partial_view() -> None:
    result = decide_care(
        LabelExtractionPayload(
            image_type="both",
            wash_permission="allowed",
            bleach_permission="prohibited",
            tumble_permission="allowed",
            iron_permission="allowed",
            dry_clean_permission="prohibited",
            overall_confidence=72,
            uncertain_fields=["wash_process"],
        )
    )

    assert result.status == "needs_review"
    assert result.confirmed_evidence == [
        "water_washing_allowed_temperature_unknown",
        "bleach_prohibited",
        "tumble_drying_allowed",
        "ironing_allowed",
        "dry_cleaning_prohibited",
    ]
