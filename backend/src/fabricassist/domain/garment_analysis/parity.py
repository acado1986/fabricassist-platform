"""Strict v2 contracts for the legacy-capability parity projections.

These models are deliberately separate from the retained v1 application DTOs.
They are the boundary for barcode enrichment, cache provenance, identity
candidates, and history/render projections in the active v2 workflow.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ParityStrictModel(BaseModel):
    """Immutable boundary model that rejects provider/catalog surprises."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BarcodeCandidateStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


class BarcodeDecoder(StrEnum):
    LOCAL = "local"
    VISION = "vision"


class BarcodeCandidateValue(ParityStrictModel):
    image_id: UUID
    raw_value: Annotated[str, Field(min_length=1, max_length=120)]
    normalized_value: Annotated[str | None, Field(max_length=32)] = None
    status: BarcodeCandidateStatus
    decoder: BarcodeDecoder
    symbology: Annotated[str | None, Field(max_length=40)] = None
    validation_code: Annotated[str | None, Field(max_length=80)] = None


class ProductFactSnapshot(ParityStrictModel):
    """Allow-listed product fields; arbitrary catalog JSON never becomes facts."""

    brand: Annotated[str | None, Field(max_length=160)] = None
    name: Annotated[str | None, Field(max_length=240)] = None
    variant: Annotated[str | None, Field(max_length=160)] = None
    category: Annotated[str | None, Field(max_length=120)] = None
    materials: tuple[Annotated[str, Field(max_length=80)], ...] = Field(
        default_factory=tuple, max_length=20
    )
    care_facts: tuple[Annotated[str, Field(max_length=160)], ...] = Field(
        default_factory=tuple, max_length=40
    )


class BarcodeLookupStatus(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    EXACT = "exact"
    PROBABLE = "probable"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    NOT_FOUND = "not_found"
    OUTAGE = "outage"


class BarcodeEnrichment(ParityStrictModel):
    """Optional, source-referenced branch output used by v2 finalization."""

    schema_version: str = "barcode-enrichment-v2"
    candidates: tuple[BarcodeCandidateValue, ...] = Field(default_factory=tuple, max_length=16)
    lookup_status: BarcodeLookupStatus = BarcodeLookupStatus.NOT_ATTEMPTED
    selected_barcode: Annotated[str | None, Field(max_length=32)] = None
    provider: Annotated[str | None, Field(max_length=100)] = None
    source_name: Annotated[str | None, Field(max_length=255)] = None
    source_reference: Annotated[str | None, Field(max_length=500)] = None
    license_name: Annotated[str | None, Field(max_length=255)] = None
    product: ProductFactSnapshot | None = None
    warnings: tuple[Annotated[str, Field(max_length=160)], ...] = Field(
        default_factory=tuple, max_length=24
    )


class MergeSource(StrEnum):
    PRIOR_ASSESSMENT = "prior_assessment"
    ACCEPTED_CORRECTION = "accepted_correction"
    NEW_BRANCH = "new_branch"


class MergeProvenance(ParityStrictModel):
    field_path: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.\[\]-]{0,159}$")]
    source: MergeSource
    source_revision_id: UUID
    source_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=16)
    authority: Annotated[str, Field(min_length=1, max_length=80)]
    selected: bool
    supersedes: tuple[UUID, ...] = Field(default_factory=tuple, max_length=16)


class CacheReuseSource(StrEnum):
    MISS = "miss"
    POSTGRES_EXACT = "postgres_exact"
    VALKEY_HOT = "valkey_hot"
    POSTGRES_CANONICAL = "postgres_canonical"
    POSTGRES_RENDERED = "postgres_rendered"


class CacheReuseProvenance(ParityStrictModel):
    source: CacheReuseSource
    key: Annotated[str, Field(min_length=1, max_length=512)]
    reused: bool
    reuse_count: Annotated[int, Field(ge=0)] = 0
    normalization_version: Annotated[str, Field(min_length=1, max_length=80)]
    schema_version: Annotated[str, Field(min_length=1, max_length=80)]
    prompt_version: Annotated[str | None, Field(max_length=80)] = None
    policy_version: Annotated[str | None, Field(max_length=80)] = None
    template_version: Annotated[str | None, Field(max_length=80)] = None


class IdentityCandidateReason(ParityStrictModel):
    code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")]
    detail: Annotated[str, Field(min_length=1, max_length=300)]
    source_image_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=8)
    matched_value: Annotated[str | None, Field(max_length=255)] = None


class ObservationProjection(ParityStrictModel):
    observation_id: UUID
    garment_id: UUID
    revision_id: UUID
    observation_type: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    stability: Annotated[str, Field(pattern=r"^(stable|condition)$")]
    value: dict[str, JsonValue]
    evidence_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=16)
    authority: Annotated[str, Field(min_length=1, max_length=80)]
    confidence: Annotated[float | None, Field(ge=0, le=100)] = None
    supersedes_observation_id: UUID | None = None


class RenderedAnswerProjection(ParityStrictModel):
    result_id: UUID
    language: Annotated[str, Field(pattern=r"^(en|es)$")]
    template_version: Annotated[str, Field(min_length=1, max_length=80)]
    validation_outcome: Annotated[str, Field(min_length=1, max_length=40)]
    sections: dict[str, JsonValue]
    provenance: tuple[Annotated[str, Field(max_length=160)], ...] = Field(
        default_factory=tuple, max_length=40
    )
    rendered_at: datetime | None = None


class ExecutionSnapshot(ParityStrictModel):
    """Immutable behavior selection captured before a revision is published."""

    schema_version: str = "execution-snapshot-v2"
    module_version: Annotated[str, Field(min_length=1, max_length=100)]
    workflow_version: Annotated[str, Field(min_length=1, max_length=100)]
    provider: Annotated[str, Field(min_length=1, max_length=100)]
    model: Annotated[str, Field(min_length=1, max_length=200)]
    prompt_versions: dict[str, Annotated[str, Field(min_length=1, max_length=100)]]
    schema_versions: dict[str, Annotated[str, Field(min_length=1, max_length=100)]]
    preprocessing_version: Annotated[str, Field(min_length=1, max_length=100)]
    branch_routing_version: Annotated[str, Field(min_length=1, max_length=100)]
    cache_version: Annotated[str, Field(min_length=1, max_length=100)]
    product_adapter_version: Annotated[str, Field(min_length=1, max_length=100)]
    identity_policy_version: Annotated[str, Field(min_length=1, max_length=100)]
    care_policy_version: Annotated[str, Field(min_length=1, max_length=100)]
    rendering_version: Annotated[str, Field(min_length=1, max_length=100)]
    effective_feature_flags: dict[str, bool] = Field(default_factory=dict)
