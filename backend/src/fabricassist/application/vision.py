"""Provider-neutral, strictly validated care-label extraction boundary."""
# Pydantic's Field default factory is dynamic at this external schema boundary.
# pyright: reportUnknownVariableType=false

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROMPT_VERSION = "care-label-extraction-v1"
SCHEMA_VERSION = "label-extraction-v1"


class MaterialFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    percentage: int | None = Field(default=None, ge=0, le=100)
    confidence: int = Field(ge=0, le=100)


class LabelExtractionPayload(BaseModel):
    """Only evidence-backed care facts may cross the provider boundary."""

    model_config = ConfigDict(extra="forbid")
    image_type: Literal["care_label", "garment", "both", "unrelated", "unusable"]
    original_visible_text: str = Field(default="", max_length=5000)
    materials: list[MaterialFact] = Field(default_factory=list, max_length=20)
    wash_permission: Literal["allowed", "prohibited", "unknown"] = "unknown"
    max_wash_temperature_c: int | None = Field(default=None, ge=10, le=95)
    wash_process: Literal["normal", "mild", "very_mild", "unknown"] = "unknown"
    bleach_permission: Literal["allowed", "prohibited", "unknown"] = "unknown"
    tumble_permission: Literal["allowed", "prohibited", "unknown"] = "unknown"
    iron_permission: Literal["allowed", "prohibited", "unknown"] = "unknown"
    dry_clean_permission: Literal["allowed", "prohibited", "unknown"] = "unknown"
    written_warnings: list[str] = Field(default_factory=list, max_length=20)
    overall_confidence: int = Field(ge=0, le=100)
    uncertain_fields: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_evidence(self) -> LabelExtractionPayload:
        if self.wash_permission == "prohibited" and self.max_wash_temperature_c is not None:
            raise ValueError("A prohibited wash instruction cannot have a wash temperature.")
        if self.image_type == "garment" and self.wash_permission != "unknown":
            raise ValueError("A garment-only image cannot authorize a care process.")
        total = sum(material.percentage or 0 for material in self.materials)  # pyright: ignore[reportUnknownVariableType]
        if total > 100:
            raise ValueError("Material percentages cannot exceed 100.")
        return self


@dataclass(frozen=True)
class NormalizedImage:
    jpeg_bytes: bytes
    sha256: str
    width: int
    height: int
    kind: Literal["garment", "care_label"] = "care_label"


@dataclass(frozen=True)
class ProviderResult:
    payload: LabelExtractionPayload
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class VisionProviderError(Exception):
    """Categorized provider failure that drives bounded worker retries."""

    def __init__(
        self,
        code: Literal["TRANSIENT", "PERMANENT", "SCHEMA", "INCOMPLETE"],
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code


class VisionExtractionProvider(Protocol):
    async def extract_label(self, images: tuple[NormalizedImage, ...]) -> ProviderResult: ...
