"""Facade implementation for the isolated garment-analysis module."""

from __future__ import annotations

from typing import Protocol

from fabricassist.application.garment_analysis.commands import (
    ReanalyzeAnalysisBranch,
    RecordAnalysisCorrection,
    RecordGarmentCleaningEvent,
    ResumeGarmentAnalysis,
    StartGarmentAnalysis,
)
from fabricassist.application.garment_analysis.ports import (
    AnalysisRepository,
    BranchReanalysisRequest,
    CleaningHistoryRepository,
    CorrectionRepository,
    GarmentAnalysisWorkflow,
    ResumeWorkflowRequest,
)
from fabricassist.application.garment_analysis.queries import (
    AnalysisProgress,
    AnalysisReference,
    CleaningEvent,
    FabricAssistAnalysisResult,
    GetGarmentAnalysis,
)


class GarmentAnalysisService(Protocol):
    """The sole future API/worker entry point for garment-analysis operations."""

    async def start_analysis(self, command: StartGarmentAnalysis) -> AnalysisReference: ...

    async def get_analysis(
        self, query: GetGarmentAnalysis
    ) -> FabricAssistAnalysisResult | AnalysisProgress: ...

    async def resume_analysis(self, command: ResumeGarmentAnalysis) -> AnalysisProgress: ...

    async def reanalyze_branch(self, command: ReanalyzeAnalysisBranch) -> AnalysisReference: ...

    async def record_cleaning_event(self, command: RecordGarmentCleaningEvent) -> CleaningEvent: ...

    async def record_user_correction(
        self, command: RecordAnalysisCorrection
    ) -> AnalysisReference: ...


class DefaultGarmentAnalysisService:
    """Coordinates ports only; no old executor is wrapped by this preparatory seam."""

    def __init__(
        self,
        *,
        analysis_repository: AnalysisRepository,
        workflow: GarmentAnalysisWorkflow,
        cleaning_history_repository: CleaningHistoryRepository,
        correction_repository: CorrectionRepository,
    ) -> None:
        self._analysis_repository = analysis_repository
        self._workflow = workflow
        self._cleaning_history_repository = cleaning_history_repository
        self._correction_repository = correction_repository

    async def start_analysis(self, command: StartGarmentAnalysis) -> AnalysisReference:
        return await self._analysis_repository.create_analysis(command)

    async def get_analysis(
        self, query: GetGarmentAnalysis
    ) -> FabricAssistAnalysisResult | AnalysisProgress:
        return await self._analysis_repository.get_analysis(query)

    async def resume_analysis(self, command: ResumeGarmentAnalysis) -> AnalysisProgress:
        result = await self._workflow.resume(
            ResumeWorkflowRequest(
                reference=AnalysisReference(
                    tenant_id=command.tenant_id,
                    scan_id=command.scan_id,
                    run_id=command.run_id,
                    revision_id=command.revision_id,
                ),
                correlation_id=command.correlation_id,
            )
        )
        if isinstance(result, AnalysisProgress):
            return result
        return AnalysisProgress(reference=result.reference, status=result.status)

    async def reanalyze_branch(self, command: ReanalyzeAnalysisBranch) -> AnalysisReference:
        reference = await self._analysis_repository.create_branch_reanalysis(command)
        await self._workflow.reanalyze_branch(
            BranchReanalysisRequest(
                reference=reference,
                branch=command.branch,
                correlation_id=command.correlation_id,
            )
        )
        return reference

    async def record_cleaning_event(self, command: RecordGarmentCleaningEvent) -> CleaningEvent:
        return await self._cleaning_history_repository.record_cleaning_event(command)

    async def record_user_correction(self, command: RecordAnalysisCorrection) -> AnalysisReference:
        return await self._correction_repository.record_correction(command)
