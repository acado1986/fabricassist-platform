"""Provider-neutral workflow and persistence ports for garment analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Generic, Protocol, TypeVar
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
from fabricassist.domain.garment_analysis.models import (
    GarmentInspection,
    LabelExtraction,
    StainTreatment,
)


@dataclass(frozen=True)
class ProviderImage:
    """Normalized image bytes authorized and routed by the caller."""

    image_id: UUID
    jpeg_bytes: bytes
    role: str
    viewpoint: str = "unknown"
    label_scope: str = "unknown"


@dataclass(frozen=True)
class GarmentInspectionRequest:
    images: tuple[ProviderImage, ...]
    attempt_number: int


@dataclass(frozen=True)
class LabelExtractionRequest:
    images: tuple[ProviderImage, ...]
    attempt_number: int


@dataclass(frozen=True)
class StainTreatmentRequest:
    images: tuple[ProviderImage, ...]
    attempt_number: int


T = TypeVar("T")


@dataclass(frozen=True)
class ModelInvocation(Generic[T]):
    value: T
    provider: str
    model: str
    prompt_version: str
    prompt_checksum: str
    schema_version: str
    latency_ms: int
    attempt_number: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    thought_tokens: int | None = None
    tool_tokens: int | None = None
    response_model_version: str | None = None
    response_id: str | None = None


class GarmentVisionProvider(Protocol):
    """Task-specific vision port; provider payloads and SDK objects never escape."""

    async def inspect_garment(
        self, request: GarmentInspectionRequest
    ) -> ModelInvocation[GarmentInspection]: ...
    async def extract_labels(
        self, request: LabelExtractionRequest
    ) -> ModelInvocation[LabelExtraction]: ...
    async def analyze_stain(
        self, request: StainTreatmentRequest
    ) -> ModelInvocation[StainTreatment]: ...


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


class FinalizationRepository(Protocol):
    """Atomically persist a deterministic v2 result once required branches settle."""

    async def finalize_if_ready(
        self, *, reference: AnalysisReference
    ) -> FabricAssistAnalysisResult | None: ...


class ImageAssetRepository(Protocol):
    """Load only authorized, already-routed normalized images for a branch.

    Implementations own the revision-image join and object-storage lookup.  A
    workflow never receives an object key, ORM image row, or a general-purpose
    storage client, which keeps concurrent branch tasks independent.
    """

    async def branch_images(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
    ) -> tuple[ProviderImage, ...]: ...


@dataclass(frozen=True)
class BranchClaim:
    """A branch lease returned only to the worker that atomically acquired it."""

    branch_result_id: UUID
    branch: AnalysisBranch
    attempt_number: int
    claim_token: UUID


@dataclass(frozen=True)
class BranchState:
    branch_result_id: UUID
    branch: AnalysisBranch
    status: str
    attempt_count: int
    lease_expires_at: datetime | None


@dataclass(frozen=True)
class BranchInvocation:
    """Safe, normalized usage metadata for a single provider call."""

    provider: str
    model: str
    prompt_version: str
    schema_version: str
    request_fingerprint: str
    image_count: int
    role_counts: Mapping[str, int]
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    thought_tokens: int | None = None
    tool_tokens: int | None = None
    response_model_version: str | None = None
    estimated_cost_usd: Decimal | None = None


@dataclass(frozen=True)
class BranchCompletion:
    """Validated terminal branch data; provider objects never cross this port."""

    status: str
    result_payload: Mapping[str, object] | None = None
    uncertain_fields: tuple[str, ...] = ()
    overall_confidence: int | None = None
    error_category: str | None = None
    invocation: BranchInvocation | None = None


class BranchStateRepository(Protocol):
    """Durable branch state for one workflow operation.

    Production implementations must open and commit a separate short unit of
    work for each method invocation.  The interface intentionally has no
    session argument because an ``AsyncSession`` must never be shared by the
    parallel garment and label tasks.
    """

    async def claim_branch(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
        request_fingerprint: str,
        lease_seconds: int,
    ) -> BranchClaim | None: ...

    async def branch_states(
        self, *, tenant_id: UUID, revision_id: UUID
    ) -> tuple[BranchState, ...]: ...

    async def complete_branch(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        claim: BranchClaim,
        completion: BranchCompletion,
    ) -> bool: ...

    async def mark_not_provided(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
    ) -> None: ...
