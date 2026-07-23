from fabricassist.application.analysis import render_rich_result
from fabricassist.application.products import PersistedProductLookup
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


def test_rich_result_preserves_sourced_product_metadata() -> None:
    out = render_rich_result(
        GarmentEvidenceDossier(),
        ProposedCarePlan(classification="provisional", cleaning=Cleaning(method="unknown")),
        CareValidationReport(outcome=ValidationOutcome.PASSED_WITH_WARNINGS),
        "en",
        PersistedProductLookup(
            barcode="4006381333931",
            status="exact",
            provider="mock",
            source_name="Mock catalog",
            source_reference="mock:4006381333931",
            license_name="test-data",
            retrieved_at=None,
            product={"name": "Cotton shirt"},
        ),
    )
    product = out["product_information"]
    assert product == {
        "barcode": "4006381333931",
        "status": "exact",
        "provider": "mock",
        "source_name": "Mock catalog",
        "source_reference": "mock:4006381333931",
        "license_name": "test-data",
        "retrieved_at": None,
        "product": {"name": "Cotton shirt"},
    }
