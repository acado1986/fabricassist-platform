from uuid import uuid4

from fabricassist.domain.care import (
    Cleaning,
    ProposedCarePlan,
    ValidationOutcome,
    validate_care_plan,
)
from fabricassist.domain.evidence import CareFact, EvidenceSource, GarmentEvidenceDossier, ImageRole


def fact(permission: str, temp: int | None = None) -> CareFact:
    return CareFact(
        code="wash",
        permission=permission,
        temperature_c=temp,
        confidence=100,
        source=EvidenceSource(image_id=uuid4(), role=ImageRole.CARE_LABEL),
    )


def test_label_prohibition_blocks_water_and_detergent() -> None:
    p = ProposedCarePlan(
        classification="definitive",
        cleaning=Cleaning(method="water_wash", maximum_temperature_c=30),
        detergent="standard",
    )
    assert (
        validate_care_plan(GarmentEvidenceDossier(care_facts=[fact("prohibited")]), p).outcome
        == ValidationOutcome.BLOCKED
    )


def test_garment_only_is_provisional() -> None:
    p = ProposedCarePlan(classification="definitive", cleaning=Cleaning(method="unknown"))
    assert validate_care_plan(GarmentEvidenceDossier(), p).outcome == ValidationOutcome.BLOCKED
