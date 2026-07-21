from __future__ import annotations

from fabricassist.application.analysis import render_result


def test_review_result_has_the_complete_answer_shape() -> None:
    answer = render_result(
        {
            "status": "needs_review",
            "actions": [],
            "prohibitions": [],
            "professional_only": [],
            "detergent": "no_domestic_detergent",
            "uncertainties": ["insufficient_label_evidence"],
        },
        "en",
    )

    assert answer["professional_only"] == []
    assert answer["detergent"] == ""
