"""Provider-neutral workflow and persistence ports for garment analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fabricassist.application.garment_analysis.commands import (
    AnalysisBranch,
    ReanalyzeAnalysisBranch,
    RecordAnalysisCorrection,
    RecordGarmentCleaningEvent,
    StartGarmentAnalysis,
)
from fabricassist.application.garment_analysis.queries import (
    AnalysisProgress,
    AnalysisReference,
    CleaningEvent,
    FabricAssistAnalysisResult,
    GetGarmentAnalysis,
)


@dataclass(frozen=True)
class GarmentAnalysisRequest:
    reference: AnalysisReference
    correlation_id: str


@dataclass(frozen=True)
class ResumeWorkflowRequest:
    reference: AnalysisReference
    correlation_id: str


@dataclass(frozen=True)
class BranchReanalysisRequest:
    reference: AnalysisReference
    branch: AnalysisBranch
    correlation_id: str


type WorkflowResult = AnalysisProgress | FabricAssistAnalysisResult


class GarmentAnalysisWorkflow(Protocol):
    """Run v2 work without exposing asyncio tasks or infrastructure objects."""

    async def execute(self, request: GarmentAnalysisRequest) -> WorkflowResult: ...

    async def resume(self, request: ResumeWorkflowRequest) -> WorkflowResult: ...

    async def reanalyze_branch(self, request: BranchReanalysisRequest) -> WorkflowResult: ...


class AnalysisRepository(Protocol):
    """Persistence boundary; implementations must enforce tenant ownership."""

    async def create_analysis(self, command: StartGarmentAnalysis) -> AnalysisReference: ...

    async def get_analysis(
        self, query: GetGarmentAnalysis
    ) -> FabricAssistAnalysisResult | AnalysisProgress: ...

    async def create_branch_reanalysis(
        self, command: ReanalyzeAnalysisBranch
    ) -> AnalysisReference: ...


class CleaningHistoryRepository(Protocol):
    async def record_cleaning_event(self, command: RecordGarmentCleaningEvent) -> CleaningEvent: ...


class CorrectionRepository(Protocol):
    async def record_correction(self, command: RecordAnalysisCorrection) -> AnalysisReference: ...


class ImageAssetRepository(Protocol):
    """Authorized image access stays behind a port and never returns storage keys."""

    async def image_ids_for_revision(
        self, *, tenant_id: UUID, revision_id: UUID
    ) -> tuple[UUID, ...]: ...
