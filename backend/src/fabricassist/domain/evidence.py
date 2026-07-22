"""Provider-independent, source referenced garment evidence."""

from __future__ import annotations

# pyright: reportUnknownVariableType=false
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImageRole(StrEnum):
    GARMENT_OVERVIEW = "garment_overview"
    CARE_LABEL = "care_label"
    COMPOSITION_LABEL = "composition_label"
    BARCODE_BRAND_LABEL = "barcode_brand_label"
    STAIN_CLOSEUP = "stain_closeup"
    DAMAGE_CLOSEUP = "damage_closeup"
    CONSTRUCTION_DETAIL = "construction_detail"
    OTHER = "other"


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: UUID
    role: ImageRole


class CareFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=80)
    permission: str = Field(pattern="^(allowed|prohibited|unknown)$")
    temperature_c: int | None = Field(default=None, ge=10, le=95)
    confidence: int = Field(ge=0, le=100)
    source: EvidenceSource
    original_text: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def no_temperature_when_prohibited(self) -> CareFact:
        if self.permission == "prohibited" and self.temperature_c is not None:
            raise ValueError("A prohibited process cannot have a temperature")
        return self


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    kind: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=5000)
    confidence: int = Field(ge=0, le=100)
    source: EvidenceSource
    time_varying: bool = False


class GarmentEvidenceDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "garment-evidence-v1"
    observations: list[Observation] = Field(default_factory=list)
    care_facts: list[CareFact] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)

    def fact(self, code: str) -> CareFact | None:
        return next((fact for fact in self.care_facts if fact.code == code), None)


class GarmentEvidenceDelta(GarmentEvidenceDossier):
    """New immutable observations; merger is deliberately deterministic."""


def merge_evidence(
    prior: GarmentEvidenceDossier | None, delta: GarmentEvidenceDelta
) -> GarmentEvidenceDossier:
    """Merge by fact code, retaining photographed prohibitions over weaker claims."""
    if prior is None:
        return GarmentEvidenceDossier(**delta.model_dump())
    facts = {fact.code: fact for fact in prior.care_facts}
    for fact in delta.care_facts:
        previous = facts.get(fact.code)
        if (
            previous is None
            or fact.confidence >= previous.confidence
            or fact.permission == "prohibited"
        ):
            facts[fact.code] = fact
    seen = {item.id for item in prior.observations}
    observations = [
        *prior.observations,
        *(item for item in delta.observations if item.id not in seen),
    ]
    return GarmentEvidenceDossier(
        observations=observations,
        care_facts=list(facts.values()),
        uncertainties=list(dict.fromkeys([*prior.uncertainties, *delta.uncertainties])),
    )
