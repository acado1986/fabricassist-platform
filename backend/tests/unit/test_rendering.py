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
    assert out["validation_state"] == "Validated with important notes"


def test_rich_result_renders_care_codes_in_spanish() -> None:
    out = render_rich_result(
        GarmentEvidenceDossier(),
        ProposedCarePlan(
            classification="provisional",
            cleaning=Cleaning(method="water_wash"),
            detergent="no_domestic_detergent",
            uncertainties=["care_label_facts_unknown"],
        ),
        CareValidationReport(
            outcome=ValidationOutcome.BLOCKED,
            violations=["LABEL_PROHIBITS_WATER_WASH"],
        ),
        "es",
    )
    assert out["validation_state"] == (
        "Las indicaciones de cuidado aún no se pueden mostrar de forma segura"
    )
    assert out["cleaning"] == {
        "method": "Lavar con agua",
        "maximum_temperature_c": None,
    }
    assert out["detergent"] == "No uses detergente doméstico"
    assert out["violations"] == ["La etiqueta indica que no se debe lavar esta prenda con agua"]
    assert out["uncertainties"] == [
        "No pudimos confirmar las indicaciones de la etiqueta de cuidado"
    ]


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
