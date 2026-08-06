"""Contract coverage for the inactive native asyncio garment workflow."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from fabricassist.application.garment_analysis.commands import AnalysisBranch
from fabricassist.application.garment_analysis.orchestration.asyncio_workflow import (
    AsyncioGarmentAnalysisWorkflow,
    GarmentAnalysisWorkflowPolicy,
)
from fabricassist.application.garment_analysis.ports import (
    BranchClaim,
    BranchCompletion,
    BranchState,
    GarmentAnalysisRequest,
    GarmentInspectionRequest,
    LabelExtractionRequest,
    ModelInvocation,
    ProviderImage,
    ResumeWorkflowRequest,
)
from fabricassist.application.garment_analysis.queries import AnalysisProgress, AnalysisReference
from fabricassist.application.vision import VisionProviderError
from fabricassist.domain.garment_analysis.models import (
    EvidenceCertainty,
    EvidenceSourceKind,
    FieldEvidence,
    GarmentInspection,
    GarmentIssue,
    GarmentIssueKind,
    IssueSeverity,
    LabelExtraction,
    Permission,
    StainTreatment,
    WashInstruction,
)
from fabricassist.infrastructure.garment_analysis.providers.fake import FakeGarmentVisionProvider


@dataclass
class StoredBranch:
    id: UUID
    status: str = "pending"
    attempt_count: int = 0
    claim_token: UUID | None = None
    lease_expires_at: datetime | None = None
    completion: BranchCompletion | None = None


class InMemoryBranchRepository:
    """Lock-backed branch store modelling the Phase 4 compare-and-set contract."""

    def __init__(self) -> None:
        self.now = datetime.now(UTC)
        self.branches: dict[AnalysisBranch, StoredBranch] = {}
        self.lock = asyncio.Lock()
        self.completed: list[AnalysisBranch] = []

    async def claim_branch(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
        request_fingerprint: str,
        lease_seconds: int,
    ) -> BranchClaim | None:
        del tenant_id, revision_id, request_fingerprint
        async with self.lock:
            stored = self.branches.setdefault(branch, StoredBranch(id=uuid4()))
            stale = (
                stored.status == "running"
                and stored.lease_expires_at is not None
                and stored.lease_expires_at <= self.now
            )
            if stored.attempt_count >= 2 or (
                stored.status not in {"pending", "retryable_failed"} and not stale
            ):
                return None
            stored.status = "running"
            stored.attempt_count += 1
            stored.claim_token = uuid4()
            stored.lease_expires_at = self.now + timedelta(seconds=lease_seconds)
            return BranchClaim(
                branch_result_id=stored.id,
                branch=branch,
                attempt_number=stored.attempt_count,
                claim_token=stored.claim_token,
            )

    async def complete_branch(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        claim: BranchClaim,
        completion: BranchCompletion,
    ) -> bool:
        del tenant_id, run_id
        async with self.lock:
            stored = self.branches[claim.branch]
            if stored.status != "running" or stored.claim_token != claim.claim_token:
                return False
            stored.status = completion.status
            stored.claim_token = None
            stored.lease_expires_at = None
            stored.completion = completion
            self.completed.append(claim.branch)
            return True

    async def branch_states(self, *, tenant_id: UUID, revision_id: UUID) -> tuple[BranchState, ...]:
        del tenant_id, revision_id
        return tuple(
            BranchState(
                branch_result_id=stored.id,
                branch=branch,
                status=stored.status,
                attempt_count=stored.attempt_count,
                lease_expires_at=stored.lease_expires_at,
                result_payload=(stored.completion.result_payload if stored.completion else None),
            )
            for branch, stored in sorted(self.branches.items(), key=lambda item: item[0].value)
        )

    async def mark_not_provided(
        self, *, tenant_id: UUID, run_id: UUID, revision_id: UUID, branch: AnalysisBranch
    ) -> None:
        del tenant_id, run_id, revision_id
        async with self.lock:
            self.branches.setdefault(branch, StoredBranch(id=uuid4(), status="not_provided"))


class InMemoryImageRepository:
    def __init__(self, images: dict[AnalysisBranch, tuple[ProviderImage, ...]]) -> None:
        self.images = images

    async def branch_images(
        self, *, tenant_id: UUID, revision_id: UUID, branch: AnalysisBranch
    ) -> tuple[ProviderImage, ...]:
        del tenant_id, revision_id
        return self.images.get(branch, ())


class RecordingProvider(FakeGarmentVisionProvider):
    def __init__(
        self,
        *,
        fail_label_once: bool = False,
        block_label: bool = False,
        block_until_both_started: bool = False,
    ) -> None:
        self.fail_label_once = fail_label_once
        self.block_label = block_label
        self.block_until_both_started = block_until_both_started
        self.calls: list[tuple[AnalysisBranch, int]] = []
        self.active = 0
        self.max_active = 0
        self.both_started = asyncio.Event()
        self.release = asyncio.Event()

    async def inspect_garment(self, request: GarmentInspectionRequest) -> ModelInvocation[Any]:
        return await self._record(
            AnalysisBranch.GARMENT_INSPECTION, request, super().inspect_garment
        )

    async def extract_labels(self, request: LabelExtractionRequest) -> ModelInvocation[Any]:
        if self.fail_label_once and request.attempt_number == 1:
            self.calls.append((AnalysisBranch.LABEL_EXTRACTION, request.attempt_number))
            raise VisionProviderError("RATE_LIMIT", "retry", provider_http_status=429)
        return await self._record(AnalysisBranch.LABEL_EXTRACTION, request, super().extract_labels)

    async def _record(
        self,
        branch: AnalysisBranch,
        request: GarmentInspectionRequest | LabelExtractionRequest,
        call: Callable[[Any], Awaitable[ModelInvocation[Any]]],
    ) -> ModelInvocation[Any]:
        self.calls.append((branch, request.attempt_number))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if len({item[0] for item in self.calls}) == 2:
            self.both_started.set()
        try:
            if self.block_until_both_started:
                await self.release.wait()
            if self.block_label and branch is AnalysisBranch.LABEL_EXTRACTION:
                await self.release.wait()
            return await call(request)
        finally:
            self.active -= 1


def _images() -> dict[AnalysisBranch, tuple[ProviderImage, ...]]:
    return {
        AnalysisBranch.GARMENT_INSPECTION: (
            ProviderImage(image_id=uuid4(), jpeg_bytes=b"garment", role="garment_overview"),
        ),
        AnalysisBranch.LABEL_EXTRACTION: (
            ProviderImage(image_id=uuid4(), jpeg_bytes=b"label", role="care_label"),
        ),
    }


def _reference() -> AnalysisReference:
    return AnalysisReference(
        tenant_id=uuid4(), scan_id=uuid4(), run_id=uuid4(), revision_id=uuid4()
    )


def _workflow(
    repository: InMemoryBranchRepository,
    images: InMemoryImageRepository,
    provider: RecordingProvider,
    *,
    lease_seconds: int = 10,
    timeout_seconds: float = 1,
    finalization_repository: object | None = None,
    stain_enabled: bool = False,
) -> AsyncioGarmentAnalysisWorkflow:
    return AsyncioGarmentAnalysisWorkflow(
        branch_repository=repository,
        image_repository=images,
        provider=provider,
        finalization_repository=finalization_repository,  # type: ignore[arg-type]
        policy=GarmentAnalysisWorkflowPolicy(
            lease_seconds=lease_seconds,
            branch_timeout_seconds=timeout_seconds,
            retry_base_delay_seconds=0,
            retry_jitter_seconds=0,
            stain_analysis_enabled=stain_enabled,
        ),
    )


def _execute_request(reference: AnalysisReference) -> GarmentAnalysisRequest:
    return GarmentAnalysisRequest(reference=reference, correlation_id="workflow-test")


def _resume_request(reference: AnalysisReference) -> ResumeWorkflowRequest:
    return ResumeWorkflowRequest(reference=reference, correlation_id="workflow-test")


@pytest.mark.asyncio
async def test_required_branches_start_concurrently_and_return_only_progress() -> None:
    repository = InMemoryBranchRepository()
    provider = RecordingProvider(block_until_both_started=True)
    workflow = _workflow(repository, InMemoryImageRepository(_images()), provider)

    task = asyncio.create_task(workflow.execute(_execute_request(_reference())))
    await asyncio.wait_for(provider.both_started.wait(), timeout=1)
    assert provider.max_active == 2
    provider.release.set()
    result = await task

    assert isinstance(result, AnalysisProgress)
    assert result.status == "processing"  # Final merge/policy is Phase 7.
    assert {progress.branch for progress in result.branches} == {
        AnalysisBranch.GARMENT_INSPECTION,
        AnalysisBranch.LABEL_EXTRACTION,
    }
    assert all(stored.status == "completed" for stored in repository.branches.values())


class RecordingFinalizationRepository:
    def __init__(self) -> None:
        self.references: list[AnalysisReference] = []

    async def finalize_if_ready(self, *, reference: AnalysisReference):
        from fabricassist.application.garment_analysis.queries import FabricAssistAnalysisResult

        self.references.append(reference)
        return FabricAssistAnalysisResult(
            reference=reference,
            status="passed",
            canonical_data={"kind": "deterministic"},
        )


@pytest.mark.asyncio
async def test_settled_required_branches_finalize_without_a_planning_call() -> None:
    repository = InMemoryBranchRepository()
    provider = RecordingProvider()
    finalization = RecordingFinalizationRepository()
    reference = _reference()

    result = await _workflow(
        repository,
        InMemoryImageRepository(_images()),
        provider,
        finalization_repository=finalization,
    ).execute(_execute_request(reference))

    assert result.status == "passed"
    assert finalization.references == [reference]
    assert provider.calls == [
        (AnalysisBranch.GARMENT_INSPECTION, 1),
        (AnalysisBranch.LABEL_EXTRACTION, 1),
    ]


@pytest.mark.asyncio
async def test_retry_is_scoped_to_the_failed_branch() -> None:
    repository = InMemoryBranchRepository()
    provider = RecordingProvider(fail_label_once=True)
    workflow = _workflow(repository, InMemoryImageRepository(_images()), provider)
    reference = _reference()

    result = await workflow.resume(_resume_request(reference))

    assert isinstance(result, AnalysisProgress)
    assert result.status == "processing"
    assert provider.calls.count((AnalysisBranch.GARMENT_INSPECTION, 1)) == 1
    assert provider.calls.count((AnalysisBranch.LABEL_EXTRACTION, 1)) == 1
    assert provider.calls.count((AnalysisBranch.LABEL_EXTRACTION, 2)) == 1
    assert repository.branches[AnalysisBranch.GARMENT_INSPECTION].attempt_count == 1
    assert repository.branches[AnalysisBranch.LABEL_EXTRACTION].attempt_count == 2


@pytest.mark.asyncio
async def test_timeout_is_retryable_once_then_becomes_a_durable_failure() -> None:
    repository = InMemoryBranchRepository()
    provider = RecordingProvider(block_label=True)
    workflow = _workflow(
        repository, InMemoryImageRepository(_images()), provider, timeout_seconds=0.01
    )

    result = await workflow.execute(_execute_request(_reference()))

    assert isinstance(result, AnalysisProgress)
    assert result.status == "failed"
    assert provider.calls.count((AnalysisBranch.GARMENT_INSPECTION, 1)) == 1
    assert provider.calls.count((AnalysisBranch.LABEL_EXTRACTION, 1)) == 1
    assert provider.calls.count((AnalysisBranch.LABEL_EXTRACTION, 2)) == 1
    assert repository.branches[AnalysisBranch.LABEL_EXTRACTION].status == "permanent_failed"


@pytest.mark.asyncio
async def test_redelivery_after_mid_fanout_crash_reuses_completed_sibling() -> None:
    repository = InMemoryBranchRepository()
    provider = RecordingProvider(block_label=True)
    images = InMemoryImageRepository(_images())
    workflow = _workflow(repository, images, provider, lease_seconds=1)
    reference = _reference()
    task = asyncio.create_task(workflow.resume(_resume_request(reference)))

    await asyncio.wait_for(provider.both_started.wait(), timeout=1)
    for _ in range(100):
        garment = repository.branches.get(AnalysisBranch.GARMENT_INSPECTION)
        if garment is not None and garment.status == "completed":
            break
        await asyncio.sleep(0)
    assert repository.branches[AnalysisBranch.GARMENT_INSPECTION].status == "completed"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    repository.now += timedelta(seconds=2)
    provider.block_label = False
    provider.release.set()
    result = await _workflow(repository, images, provider, lease_seconds=1).resume(
        _resume_request(reference)
    )

    assert isinstance(result, AnalysisProgress)
    assert result.status == "processing"
    assert provider.calls == [
        (AnalysisBranch.GARMENT_INSPECTION, 1),
        (AnalysisBranch.LABEL_EXTRACTION, 1),
        (AnalysisBranch.LABEL_EXTRACTION, 2),
    ]


@pytest.mark.asyncio
async def test_absent_logical_label_branch_is_not_provided_without_provider_attempt() -> None:
    repository = InMemoryBranchRepository()
    images = _images()
    images[AnalysisBranch.LABEL_EXTRACTION] = ()
    provider = RecordingProvider()

    result = await _workflow(repository, InMemoryImageRepository(images), provider).execute(
        _execute_request(_reference())
    )

    assert isinstance(result, AnalysisProgress)
    assert result.status == "needs_better_image"
    assert repository.branches[AnalysisBranch.LABEL_EXTRACTION].attempt_count == 0
    assert (AnalysisBranch.LABEL_EXTRACTION, 1) not in provider.calls


@pytest.mark.asyncio
async def test_concurrent_duplicate_deliveries_claim_each_branch_once() -> None:
    repository = InMemoryBranchRepository()
    images = InMemoryImageRepository(_images())
    provider = RecordingProvider()
    reference = _reference()
    first = _workflow(repository, images, provider)
    second = _workflow(repository, images, provider)

    await asyncio.gather(
        first.execute(_execute_request(reference)),
        second.resume(_resume_request(reference)),
    )

    assert sorted(provider.calls) == sorted(
        [
            (AnalysisBranch.GARMENT_INSPECTION, 1),
            (AnalysisBranch.LABEL_EXTRACTION, 1),
        ]
    )


def _stain_evidence(field: str) -> FieldEvidence:
    return FieldEvidence(
        field_path=field,
        source_kind=EvidenceSourceKind.PHOTOGRAPHED_LABEL,
        source_image_ids=(uuid4(),),
        certainty=EvidenceCertainty.OBSERVED,
        confidence=99,
    )


class EligibleStainProvider(RecordingProvider):
    def __init__(self, *, fail_stain_once: bool = False) -> None:
        super().__init__()
        self.fail_stain_once = fail_stain_once

    async def inspect_garment(self, request: GarmentInspectionRequest) -> ModelInvocation[Any]:
        self.calls.append((AnalysisBranch.GARMENT_INSPECTION, request.attempt_number))
        issue = GarmentIssue(
            issue_id=uuid4(),
            kind=GarmentIssueKind.STAIN,
            severity=IssueSeverity.MINOR,
            location="front",
            observed_description="visible spot",
            confidence=90,
            source_image_ids=(request.images[0].image_id,),
        )
        return ModelInvocation(
            value=GarmentInspection(overall_confidence=90, issues=(issue,)),
            provider="mock",
            model="test",
            prompt_version="test",
            prompt_checksum="test",
            schema_version="garment-inspection-v2",
            latency_ms=0,
            attempt_number=request.attempt_number,
        )

    async def extract_labels(self, request: LabelExtractionRequest) -> ModelInvocation[Any]:
        self.calls.append((AnalysisBranch.LABEL_EXTRACTION, request.attempt_number))
        return ModelInvocation(
            value=LabelExtraction(
                wash=WashInstruction(
                    permission=Permission.ALLOWED,
                    maximum_temperature_c=30,
                    evidence=_stain_evidence("care.wash"),
                ),
                overall_confidence=90,
            ),
            provider="mock",
            model="test",
            prompt_version="test",
            prompt_checksum="test",
            schema_version="label-extraction-v2",
            latency_ms=0,
            attempt_number=request.attempt_number,
        )

    async def analyze_stain(self, request: Any) -> ModelInvocation[Any]:
        self.calls.append((AnalysisBranch.STAIN_TREATMENT, request.attempt_number))
        if self.fail_stain_once and request.attempt_number == 1:
            raise VisionProviderError("RATE_LIMIT", "retry", provider_http_status=429)
        return ModelInvocation(
            value=StainTreatment(treatment_id=uuid4(), overall_confidence=70),
            provider="mock",
            model="test",
            prompt_version="test",
            prompt_checksum="test",
            schema_version="stain-treatment-v2",
            latency_ms=0,
            attempt_number=request.attempt_number,
        )


def _images_with_stain(
    *, quality_state: str = "unknown"
) -> dict[AnalysisBranch, tuple[ProviderImage, ...]]:
    images = _images()
    images[AnalysisBranch.STAIN_TREATMENT] = (
        ProviderImage(
            image_id=uuid4(),
            jpeg_bytes=b"stain",
            role="stain_closeup",
            quality_state=quality_state,
        ),
    )
    return images


@pytest.mark.asyncio
async def test_conditional_stain_branch_is_skipped_without_stain_image() -> None:
    repository = InMemoryBranchRepository()
    provider = EligibleStainProvider()
    result = await _workflow(
        repository,
        InMemoryImageRepository(_images()),
        provider,
        stain_enabled=True,
    ).execute(_execute_request(_reference()))

    assert isinstance(result, AnalysisProgress)
    assert (AnalysisBranch.STAIN_TREATMENT, 1) not in provider.calls
    assert repository.branches[AnalysisBranch.STAIN_TREATMENT].status == "not_provided"


@pytest.mark.asyncio
async def test_conditional_stain_branch_rejects_borderline_input() -> None:
    repository = InMemoryBranchRepository()
    provider = EligibleStainProvider()
    result = await _workflow(
        repository,
        InMemoryImageRepository(_images_with_stain(quality_state="borderline")),
        provider,
        stain_enabled=True,
    ).execute(_execute_request(_reference()))

    assert isinstance(result, AnalysisProgress)
    assert (AnalysisBranch.STAIN_TREATMENT, 1) not in provider.calls


@pytest.mark.asyncio
async def test_conditional_stain_branch_retries_only_the_optional_branch() -> None:
    repository = InMemoryBranchRepository()
    provider = EligibleStainProvider(fail_stain_once=True)
    result = await _workflow(
        repository,
        InMemoryImageRepository(_images_with_stain()),
        provider,
        stain_enabled=True,
    ).execute(_execute_request(_reference()))

    assert isinstance(result, AnalysisProgress)
    assert provider.calls.count((AnalysisBranch.STAIN_TREATMENT, 1)) == 1
    assert provider.calls.count((AnalysisBranch.STAIN_TREATMENT, 2)) == 1
    assert provider.calls.count((AnalysisBranch.GARMENT_INSPECTION, 1)) == 1
    assert provider.calls.count((AnalysisBranch.LABEL_EXTRACTION, 1)) == 1
    assert repository.branches[AnalysisBranch.STAIN_TREATMENT].status == "completed"
