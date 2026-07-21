"""Small deterministic v1 care decision evaluator.

It intentionally consumes validated facts only and never model-generated prose.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from fabricassist.application.vision import LabelExtractionPayload

CARE_RULES_VERSION = "care-v1"
DETERGENT_RULES_VERSION = "detergent-v1"


class CanonicalCareResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "needs_review"]
    actions: list[str] = Field(default_factory=list)
    prohibitions: list[str] = Field(default_factory=list)
    professional_only: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    detergent: str
    wash_temperature_c: int | None = None


def decide_care(extraction: LabelExtractionPayload) -> CanonicalCareResult:
    """Apply prohibition-first rules; insufficient evidence always requires review."""
    uncertainties = list(extraction.uncertain_fields)
    if extraction.image_type != "care_label" or extraction.overall_confidence < 70:
        return CanonicalCareResult(
            status="needs_review",
            uncertainties=uncertainties or ["insufficient_label_evidence"],
            detergent="no_domestic_detergent",
        )
    if extraction.wash_permission == "prohibited":
        professional_only: list[str] = []
        if extraction.dry_clean_permission == "allowed":
            professional_only.append("consult_professional_cleaner")
        return CanonicalCareResult(
            status="completed",
            prohibitions=["do_not_wash_in_water"],
            professional_only=professional_only,
            uncertainties=uncertainties,
            detergent="no_domestic_detergent",
        )
    if extraction.wash_permission != "allowed" or extraction.max_wash_temperature_c is None:
        return CanonicalCareResult(
            status="needs_review",
            uncertainties=uncertainties or ["wash_instruction_unknown"],
            detergent="no_domestic_detergent",
        )
    actions = ["wash_in_water"]
    prohibitions: list[str] = []
    if extraction.bleach_permission == "prohibited":
        prohibitions.append("do_not_bleach")
    if extraction.tumble_permission == "prohibited":
        prohibitions.append("do_not_tumble_dry")
    if extraction.iron_permission == "prohibited":
        prohibitions.append("do_not_iron")
    detergent = (
        "delicates_detergent"
        if extraction.wash_process != "normal"
        else "standard_colour_detergent"
    )
    return CanonicalCareResult(
        status="completed",
        actions=actions,
        prohibitions=prohibitions,
        uncertainties=uncertainties,
        detergent=detergent,
        wash_temperature_c=extraction.max_wash_temperature_c,
    )
