"""Read contracts for the garment-analysis module seam."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from fabricassist.application.garment_analysis.commands import AnalysisBranch


def _empty_data() -> dict[str, object]:
    return {}


@dataclass(frozen=True)
class GetGarmentAnalysis:
    tenant_id: UUID
    user_id: UUID
    scan_id: UUID
    run_id: UUID | None = None
    revision_id: UUID | None = None


@dataclass(frozen=True)
class AnalysisReference:
    """Stable identifiers returned by module commands without ORM leakage."""

    tenant_id: UUID
    scan_id: UUID
    run_id: UUID
    revision_id: UUID


@dataclass(frozen=True)
class BranchProgress:
    branch: AnalysisBranch
    status: str


@dataclass(frozen=True)
class AnalysisProgress:
    reference: AnalysisReference
    status: str
    branches: tuple[BranchProgress, ...] = ()


@dataclass(frozen=True)
class FabricAssistAnalysisResult:
    """Temporary canonical-result envelope pending Phase 2 typed domain models."""

    reference: AnalysisReference
    status: str
    canonical_data: Mapping[str, object] = field(default_factory=_empty_data)


@dataclass(frozen=True)
class CleaningEvent:
    id: UUID
    garment_id: UUID
    details: Mapping[str, object] = field(default_factory=_empty_data)
