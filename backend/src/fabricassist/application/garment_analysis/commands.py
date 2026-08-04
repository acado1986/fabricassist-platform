"""Transport-neutral commands for the garment-analysis module seam."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


def _empty_details() -> dict[str, object]:
    return {}


class AnalysisBranch(StrEnum):
    """Stable branch names; these are not orchestration implementation details."""

    GARMENT_INSPECTION = "garment_inspection"
    LABEL_EXTRACTION = "label_extraction"
    STAIN_TREATMENT = "stain_treatment"
    BARCODE_ENRICHMENT = "barcode_enrichment"


@dataclass(frozen=True)
class StartGarmentAnalysis:
    tenant_id: UUID
    user_id: UUID
    scan_id: UUID
    correlation_id: str


@dataclass(frozen=True)
class ResumeGarmentAnalysis:
    tenant_id: UUID
    scan_id: UUID
    run_id: UUID
    revision_id: UUID
    correlation_id: str


@dataclass(frozen=True)
class ReanalyzeAnalysisBranch:
    tenant_id: UUID
    user_id: UUID
    scan_id: UUID
    run_id: UUID
    revision_id: UUID
    branch: AnalysisBranch
    correlation_id: str


@dataclass(frozen=True)
class RecordGarmentCleaningEvent:
    """A future persistence command; details stay opaque until the v2 domain slice."""

    tenant_id: UUID
    user_id: UUID
    garment_id: UUID
    correlation_id: str
    details: Mapping[str, object] = field(default_factory=_empty_details)


@dataclass(frozen=True)
class RecordAnalysisCorrection:
    """A future append-only correction command; it never mutates model output."""

    tenant_id: UUID
    user_id: UUID
    scan_id: UUID
    revision_id: UUID
    correlation_id: str
    correction: Mapping[str, object] = field(default_factory=_empty_details)
