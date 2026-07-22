from uuid import uuid4

import pytest

from fabricassist.domain.care import (
    Cleaning,
    ProposedCarePlan,
    ValidationOutcome,
    validate_care_plan,
)
from fabricassist.domain.evidence import (
    CareFact,
    EvidenceSource,
    GarmentEvidenceDossier,
    ImageRole,
    Observation,
)


def fact(code: str, permission: str, temp: int | None = None) -> CareFact:
    return CareFact(
        code=code,
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
        validate_care_plan(
            GarmentEvidenceDossier(care_facts=[fact("wash", "prohibited")]), p
        ).outcome
        == ValidationOutcome.BLOCKED
    )


def test_garment_only_is_provisional() -> None:
    p = ProposedCarePlan(classification="definitive", cleaning=Cleaning(method="unknown"))
    assert validate_care_plan(GarmentEvidenceDossier(), p).outcome == ValidationOutcome.BLOCKED


@pytest.mark.parametrize(
    ("dossier", "proposal", "violation"),
    [
        (
            GarmentEvidenceDossier(care_facts=[fact("wash", "allowed", 30)]),
            ProposedCarePlan(
                classification="definitive",
                cleaning=Cleaning(method="water_wash", maximum_temperature_c=40),
            ),
            "WASH_TEMPERATURE_EXCEEDS_LABEL",
        ),
        (
            GarmentEvidenceDossier(care_facts=[fact("dry_clean", "prohibited")]),
            ProposedCarePlan(
                classification="definitive",
                cleaning=Cleaning(method="professional_dry_clean"),
            ),
            "LABEL_PROHIBITS_DRY_CLEAN",
        ),
        (
            GarmentEvidenceDossier(care_facts=[fact("wash", "allowed")]),
            ProposedCarePlan(
                classification="definitive",
                cleaning=Cleaning(method="water_wash"),
                stain_guidance=["apply a professional solvent at home"],
            ),
            "NO_CONSUMER_PROFESSIONAL_SOLVENTS",
        ),
    ],
)
def test_validator_blocks_explicit_unsafe_actions(
    dossier: GarmentEvidenceDossier, proposal: ProposedCarePlan, violation: str
) -> None:
    report = validate_care_plan(dossier, proposal)

    assert report.outcome == ValidationOutcome.BLOCKED
    assert violation in report.violations


def test_sensitive_material_requires_review_without_rewriting_the_plan() -> None:
    source = EvidenceSource(image_id=uuid4(), role=ImageRole.GARMENT_OVERVIEW)
    dossier = GarmentEvidenceDossier(
        observations=[
            Observation(id=uuid4(), kind="leather", value="visible", confidence=90, source=source)
        ]
    )
    proposal = ProposedCarePlan(classification="provisional", cleaning=Cleaning(method="unknown"))

    report = validate_care_plan(dossier, proposal)

    assert report.outcome == ValidationOutcome.NEEDS_REVIEW
    assert proposal.cleaning.method == "unknown"
