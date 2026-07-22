from fabricassist.application.analysis import render_rich_result
from fabricassist.domain.care import (
    CareValidationReport,
    Cleaning,
    ProposedCarePlan,
    ValidationOutcome,
)
from fabricassist.domain.evidence import GarmentEvidenceDossier


def test_rich_result_keeps_validation_state() -> None:
    out = render_rich_result(
        GarmentEvidenceDossier(),
        ProposedCarePlan(classification="provisional", cleaning=Cleaning(method="unknown")),
        CareValidationReport(outcome=ValidationOutcome.PASSED_WITH_WARNINGS),
        "en",
    )
    assert out["validation_state"] == "passed_with_warnings"
