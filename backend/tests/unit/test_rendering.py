from __future__ import annotations

from fabricassist.application.analysis import render_result


def test_review_result_explains_unconfirmed_evidence_without_requesting_a_clearer_photo() -> None:
    answer = render_result(
        {
            "status": "needs_review",
            "actions": [],
            "prohibitions": [],
            "professional_only": [],
            "detergent": "no_domestic_detergent",
            "confirmed_evidence": [
                "water_washing_allowed_temperature_unknown",
                "bleach_prohibited",
            ],
            "uncertainties": ["insufficient_label_evidence"],
        },
        "en",
    )

    assert answer["title"] == "We need to verify some details"
    assert answer["professional_only"] == []
    assert answer["detergent"] == ""
    assert answer["uncertainties"] == ["We could not verify enough care-label symbols."]
    assert answer["can_continue"] is True
    assert answer["confirmed_evidence"] == [
        "The label allows water washing, but we could not confirm the temperature.",
        "Do not bleach.",
    ]


def test_clearer_photo_result_is_reserved_for_image_quality_failures() -> None:
    answer = render_result(
        {
            "status": "needs_better_image",
            "actions": [],
            "prohibitions": [],
            "professional_only": [],
            "detergent": "no_domestic_detergent",
            "uncertainties": ["original_visible_text"],
        },
        "es",
    )

    assert answer["title"] == "Necesitamos una foto más clara"
    assert answer["uncertainties"] == ["No pudimos leer todo el texto visible de la etiqueta."]


def test_completed_result_renders_standard_colour_detergent() -> None:
    answer = render_result(
        {
            "status": "completed",
            "actions": ["wash_in_water"],
            "prohibitions": ["do_not_bleach"],
            "professional_only": [],
            "detergent": "standard_colour_detergent",
            "wash_temperature_c": 30,
            "uncertainties": ["wash_process"],
        },
        "en",
    )

    assert answer["actions"] == ["Wash in water at a maximum of 30 °C."]
    assert answer["prohibitions"] == ["Do not bleach."]
    assert answer["detergent"] == "Standard colour-safe detergent."
    assert answer["uncertainties"] == ["We could not confirm the wash cycle."]
