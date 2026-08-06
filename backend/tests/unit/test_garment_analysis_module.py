"""Contract tests for the inactive garment-analysis module seam."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from fabricassist.application.garment_analysis import (
    AnalysisBranch,
    AnalysisProgress,
    AnalysisReference,
    CleaningEvent,
    DefaultGarmentAnalysisService,
    GetGarmentAnalysis,
    ReanalyzeAnalysisBranch,
    RecordAnalysisCorrection,
    RecordGarmentCleaningEvent,
    ResumeGarmentAnalysis,
    StartGarmentAnalysis,
)
from fabricassist.application.garment_analysis.ports import (
    BranchReanalysisRequest,
    GarmentAnalysisRequest,
    ResumeWorkflowRequest,
)
from fabricassist.application.garment_analysis.queries import FabricAssistAnalysisResult

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "garment_analysis"


class InMemoryAnalysisRepository:
    def __init__(self, reference: AnalysisReference) -> None:
        self.reference = reference
        self.created: list[StartGarmentAnalysis] = []
        self.reanalyses: list[ReanalyzeAnalysisBranch] = []

    async def create_analysis(self, command: StartGarmentAnalysis) -> AnalysisReference:
        self.created.append(command)
        return self.reference

    async def get_analysis(
        self, query: GetGarmentAnalysis
    ) -> FabricAssistAnalysisResult | AnalysisProgress:
        del query
        return AnalysisProgress(reference=self.reference, status="queued")

    async def create_branch_reanalysis(self, command: ReanalyzeAnalysisBranch) -> AnalysisReference:
        self.reanalyses.append(command)
        return self.reference


class FakeWorkflow:
    def __init__(self, reference: AnalysisReference) -> None:
        self.reference = reference
        self.executed: list[GarmentAnalysisRequest] = []
        self.resumed: list[ResumeWorkflowRequest] = []
        self.reanalyzed: list[BranchReanalysisRequest] = []

    async def execute(self, request: GarmentAnalysisRequest) -> AnalysisProgress:
        self.executed.append(request)
        return AnalysisProgress(reference=request.reference, status="queued")

    async def resume(self, request: ResumeWorkflowRequest) -> AnalysisProgress:
        self.resumed.append(request)
        return AnalysisProgress(reference=request.reference, status="processing")

    async def reanalyze_branch(self, request: BranchReanalysisRequest) -> AnalysisProgress:
        self.reanalyzed.append(request)
        return AnalysisProgress(reference=request.reference, status="queued")


class InMemoryCleaningHistoryRepository:
    async def record_cleaning_event(self, command: RecordGarmentCleaningEvent) -> CleaningEvent:
        return CleaningEvent(id=uuid4(), garment_id=command.garment_id, details=command.details)


class InMemoryCorrectionRepository:
    def __init__(self, reference: AnalysisReference) -> None:
        self.reference = reference
        self.corrections: list[RecordAnalysisCorrection] = []

    async def record_correction(self, command: RecordAnalysisCorrection) -> AnalysisReference:
        self.corrections.append(command)
        return self.reference


@pytest.fixture
def ids() -> tuple[UUID, UUID, UUID, UUID, UUID]:
    return (uuid4(), uuid4(), uuid4(), uuid4(), uuid4())


@pytest.fixture
def service(ids: tuple[UUID, UUID, UUID, UUID, UUID]) -> DefaultGarmentAnalysisService:
    scan_id, run_id, revision_id, tenant_id, _user_id = ids
    reference = AnalysisReference(
        tenant_id=tenant_id,
        scan_id=scan_id,
        run_id=run_id,
        revision_id=revision_id,
    )
    return DefaultGarmentAnalysisService(
        analysis_repository=InMemoryAnalysisRepository(reference),
        workflow=FakeWorkflow(reference),
        cleaning_history_repository=InMemoryCleaningHistoryRepository(),
        correction_repository=InMemoryCorrectionRepository(reference),
    )


@pytest.mark.asyncio
async def test_facade_delegates_to_fake_ports_without_old_executor(
    service: DefaultGarmentAnalysisService,
    ids: tuple[UUID, UUID, UUID, UUID, UUID],
) -> None:
    scan_id, run_id, revision_id, tenant_id, user_id = ids

    started = await service.start_analysis(
        StartGarmentAnalysis(
            tenant_id=tenant_id,
            user_id=user_id,
            scan_id=scan_id,
            correlation_id="start-1",
        )
    )
    resumed = await service.resume_analysis(
        ResumeGarmentAnalysis(
            tenant_id=tenant_id,
            scan_id=scan_id,
            run_id=run_id,
            revision_id=revision_id,
            correlation_id="resume-1",
        )
    )
    reanalyzed = await service.reanalyze_branch(
        ReanalyzeAnalysisBranch(
            tenant_id=tenant_id,
            user_id=user_id,
            scan_id=scan_id,
            run_id=run_id,
            revision_id=revision_id,
            branch=AnalysisBranch.LABEL_EXTRACTION,
            correlation_id="branch-1",
        )
    )

    assert started == reanalyzed
    assert resumed.reference == started
    assert resumed.status == "processing"


@pytest.mark.asyncio
async def test_facade_exposes_query_history_and_correction_contracts(
    service: DefaultGarmentAnalysisService,
    ids: tuple[UUID, UUID, UUID, UUID, UUID],
) -> None:
    scan_id, _run_id, revision_id, tenant_id, user_id = ids
    garment_id = uuid4()

    progress = await service.get_analysis(
        GetGarmentAnalysis(tenant_id=tenant_id, user_id=user_id, scan_id=scan_id)
    )
    event = await service.record_cleaning_event(
        RecordGarmentCleaningEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            garment_id=garment_id,
            correlation_id="event-1",
            details={"method": "unknown"},
        )
    )
    correction = await service.record_user_correction(
        RecordAnalysisCorrection(
            tenant_id=tenant_id,
            user_id=user_id,
            scan_id=scan_id,
            revision_id=revision_id,
            correlation_id="correction-1",
        )
    )

    assert isinstance(progress, AnalysisProgress)
    assert event.garment_id == garment_id
    assert correction.scan_id == scan_id


def test_current_executor_characterization_fixture_is_the_v2_workflow() -> None:
    """The worker seam exposes only the public v2 workflow protocol."""
    from fabricassist.application.garment_analysis import GarmentAnalysisWorkflow

    fixture = cast(
        dict[str, object],
        json.loads((FIXTURES / "current_executor_contract.json").read_text()),
    )
    assert fixture["executor"] == (
        "fabricassist.application.garment_analysis.GarmentAnalysisWorkflow"
    )
    required_parameters = fixture["required_keyword_parameters"]
    assert isinstance(required_parameters, list)
    typed_parameters: list[str] = []
    for parameter in cast(list[object], required_parameters):
        assert isinstance(parameter, str)
        typed_parameters.append(parameter)
    assert set(typed_parameters).issubset(
        inspect.signature(GarmentAnalysisWorkflow.execute).parameters
    )
