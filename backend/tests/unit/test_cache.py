from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from PIL import Image

from fabricassist.application.cache import (
    canonical_plan_signature,
    perceptual_hash,
    uncached_images,
)
from fabricassist.application.vision import NormalizedImage
from fabricassist.domain.care import (
    CareValidationReport,
    Cleaning,
    ProposedCarePlan,
    ValidationOutcome,
)
from fabricassist.domain.evidence import GarmentEvidenceDossier, ImageRole


def normalized_image(role: ImageRole, color: str = "white") -> NormalizedImage:
    stream = BytesIO()
    Image.new("RGB", (400, 400), color).save(stream, "JPEG")
    data = stream.getvalue()
    return NormalizedImage(
        image_id=uuid4(),
        jpeg_bytes=data,
        sha256=f"{role.value}-{color}",
        width=400,
        height=400,
        role=role,
    )


def proposal() -> ProposedCarePlan:
    return ProposedCarePlan(classification="provisional", cleaning=Cleaning(method="unknown"))


def report() -> CareValidationReport:
    return CareValidationReport(
        outcome=ValidationOutcome.PASSED_WITH_WARNINGS, warnings=["unknown"]
    )


def test_exact_cache_selects_only_new_images_and_never_uses_a_phash_candidate() -> None:
    cached = normalized_image(ImageRole.CARE_LABEL)
    similar_but_crossed_symbol = normalized_image(ImageRole.CARE_LABEL, "#fefefe")
    assert perceptual_hash(cached) == perceptual_hash(similar_but_crossed_symbol)
    assert uncached_images(
        (cached, similar_but_crossed_symbol), {(cached.sha256, cached.role.value)}
    ) == (similar_but_crossed_symbol,)


def test_canonical_signature_changes_when_safety_or_product_versions_change() -> None:
    dossier = GarmentEvidenceDossier(uncertainties=["care_label_facts_unknown"])
    base = canonical_plan_signature(dossier, proposal(), report(), "product-a")
    assert base != canonical_plan_signature(dossier, proposal(), report(), "product-b")
    changed_report = CareValidationReport(outcome=ValidationOutcome.BLOCKED, violations=["BLOCK"])
    assert base != canonical_plan_signature(dossier, proposal(), changed_report, "product-a")
