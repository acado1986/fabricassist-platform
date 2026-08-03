"""Fixed, durable native-asyncio workflow for the v2 required branches.

This module deliberately implements only the inspection/label fan-out.  It is
not selected by production routes or workers until the coordinated v2 cutover.
Its recovery facts live exclusively in ``analysis_branch_results``; in-memory
tasks are used only while a single delivery is alive.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from random import uniform
from typing import Final

from fabricassist.application.garment_analysis.commands import AnalysisBranch
from fabricassist.application.garment_analysis.ports import (
    BranchClaim,
    BranchCompletion,
    BranchInvocation,
    BranchReanalysisRequest,
    BranchState,
    BranchStateRepository,
    GarmentAnalysisRequest,
    GarmentInspectionRequest,
    GarmentVisionProvider,
    ImageAssetRepository,
    LabelExtractionRequest,
    ModelInvocation,
    ProviderImage,
    ResumeWorkflowRequest,
    WorkflowResult,
)
from fabricassist.application.garment_analysis.queries import (
    AnalysisProgress,
    AnalysisReference,
    BranchProgress,
)
from fabricassist.application.vision import VisionProviderError
from fabricassist.domain.garment_analysis.models import (
    GarmentInspection,
    LabelExtraction,
)

_REQUIRED_BRANCHES: Final = (
    AnalysisBranch.GARMENT_INSPECTION,
    AnalysisBranch.LABEL_EXTRACTION,
)
_RETRYABLE_CODES: Final = frozenset(
    {
        "TIMEOUT",
        "RATE_LIMIT",
        "NETWORK",
        "UNAVAILABLE",
        "VISION_PROVIDER_INVALID_OUTPUT",
        "VISION_PROVIDER_MALFORMED_RESPONSE",
    }
)


@dataclass(frozen=True)
class GarmentAnalysisWorkflowPolicy:
    """Bounded execution policy pinned by the revision in production later."""

    lease_seconds: int = 300
    branch_timeout_seconds: float = 120
    max_model_attempts: int = 2
    retry_base_delay_seconds: float = 0.25
    retry_jitter_seconds: float = 0.1

    def __post_init__(self) -> None:
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if self.branch_timeout_seconds <= 0:
            raise ValueError("branch_timeout_seconds must be positive")
        # The Phase 4 schema and the approved retry policy are deliberately a
        # fixed initial call plus one retry, not a tunable production multiplier.
        if self.max_model_attempts != 2:
            raise ValueError("max_model_attempts must remain exactly two")
        if self.retry_base_delay_seconds < 0 or self.retry_jitter_seconds < 0:
            raise ValueError("retry delays must not be negative")


class AsyncioGarmentAnalysisWorkflow:
    """Run independent required branches with durable, branch-scoped recovery."""

    def __init__(
        self,
        *,
        branch_repository: BranchStateRepository,
        image_repository: ImageAssetRepository,
        provider: GarmentVisionProvider,
        policy: GarmentAnalysisWorkflowPolicy | None = None,
    ) -> None:
        self._branch_repository = branch_repository
        self._image_repository = image_repository
        self._provider = provider
        self._policy = policy or GarmentAnalysisWorkflowPolicy()

    async def execute(self, request: GarmentAnalysisRequest) -> WorkflowResult:
        return await self._run_required(request.reference)

    async def resume(self, request: ResumeWorkflowRequest) -> WorkflowResult:
        return await self._run_required(request.reference)

    async def reanalyze_branch(self, request: BranchReanalysisRequest) -> WorkflowResult:
        # Reanalysis repository creation supplies a successor revision.  Thus a
        # completed source branch can never be overwritten by this invocation.
        await self._run_branches(request.reference, (request.branch,))
        return await self._progress(request.reference)

    async def _run_required(self, reference: AnalysisReference) -> WorkflowResult:
        await self._run_branches(reference, _REQUIRED_BRANCHES)
        return await self._progress(reference)

    async def _run_branches(
        self, reference: AnalysisReference, branches: tuple[AnalysisBranch, ...]
    ) -> None:
        # ``TaskGroup`` keeps the task lifetime inside this call.  Branch
        # wrappers classify ordinary provider failures themselves, so a failed
        # label never cancels a successful garment sibling.
        async with asyncio.TaskGroup() as group:
            for branch in branches:
                group.create_task(self._run_branch(reference, branch), name=branch.value)

    async def _run_branch(self, reference: AnalysisReference, branch: AnalysisBranch) -> None:
        images = await self._image_repository.branch_images(
            tenant_id=self._tenant_id(reference),
            revision_id=reference.revision_id,
            branch=branch,
        )
        if not images:
            await self._branch_repository.mark_not_provided(
                tenant_id=self._tenant_id(reference),
                run_id=reference.run_id,
                revision_id=reference.revision_id,
                branch=branch,
            )
            return

        fingerprint = _request_fingerprint(branch, images)
        while True:
            claim = await self._branch_repository.claim_branch(
                tenant_id=self._tenant_id(reference),
                revision_id=reference.revision_id,
                branch=branch,
                request_fingerprint=fingerprint,
                lease_seconds=self._policy.lease_seconds,
            )
            if claim is None:
                return
            try:
                invocation = await self._invoke(branch, images, claim)
            except asyncio.CancelledError:
                # A process/worker cancellation must leave the active lease in
                # place.  A redelivery can reclaim it only after the lease, so a
                # late response cannot overwrite a newer attempt.
                raise
            except Exception as error:
                retryable, category = _classify_provider_failure(error)
                status = (
                    "retryable_failed"
                    if retryable and claim.attempt_number < self._policy.max_model_attempts
                    else "permanent_failed"
                )
                completed = await self._branch_repository.complete_branch(
                    tenant_id=self._tenant_id(reference),
                    run_id=reference.run_id,
                    claim=claim,
                    completion=BranchCompletion(status=status, error_category=category),
                )
                if not completed or status != "retryable_failed":
                    return
                await self._retry_delay(claim.attempt_number)
                continue

            completion = _success_completion(invocation, fingerprint, images)
            await self._branch_repository.complete_branch(
                tenant_id=self._tenant_id(reference),
                run_id=reference.run_id,
                claim=claim,
                completion=completion,
            )
            return

    async def _invoke(
        self,
        branch: AnalysisBranch,
        images: tuple[ProviderImage, ...],
        claim: BranchClaim,
    ) -> ModelInvocation[GarmentInspection] | ModelInvocation[LabelExtraction]:
        async with asyncio.timeout(self._policy.branch_timeout_seconds):
            if branch is AnalysisBranch.GARMENT_INSPECTION:
                return await self._provider.inspect_garment(
                    GarmentInspectionRequest(images=images, attempt_number=claim.attempt_number)
                )
            if branch is AnalysisBranch.LABEL_EXTRACTION:
                return await self._provider.extract_labels(
                    LabelExtractionRequest(images=images, attempt_number=claim.attempt_number)
                )
        raise ValueError(f"Unsupported Phase 6 branch: {branch}")

    async def _retry_delay(self, completed_attempt: int) -> None:
        delay = self._policy.retry_base_delay_seconds * (2 ** (completed_attempt - 1))
        if self._policy.retry_jitter_seconds:
            delay += uniform(0, self._policy.retry_jitter_seconds)
        if delay:
            await asyncio.sleep(delay)

    async def _progress(self, reference: AnalysisReference) -> AnalysisProgress:
        states = await self._branch_repository.branch_states(
            tenant_id=self._tenant_id(reference), revision_id=reference.revision_id
        )
        progress = AnalysisProgress(
            reference=reference,
            status=_stable_progress_status(states),
            branches=tuple(
                BranchProgress(branch=state.branch, status=state.status) for state in states
            ),
        )
        return progress

    @staticmethod
    def _tenant_id(reference: AnalysisReference):
        return reference.tenant_id


def _request_fingerprint(branch: AnalysisBranch, images: tuple[ProviderImage, ...]) -> str:
    """Hash routed immutable image metadata without logging or retaining bytes."""
    value = {
        "branch": branch.value,
        "images": [
            {
                "id": str(image.image_id),
                "role": image.role,
                "viewpoint": image.viewpoint,
                "label_scope": image.label_scope,
                "sha256": hashlib.sha256(image.jpeg_bytes).hexdigest(),
            }
            for image in images
        ],
    }
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def _success_completion(
    invocation: ModelInvocation[GarmentInspection] | ModelInvocation[LabelExtraction],
    request_fingerprint: str,
    images: tuple[ProviderImage, ...],
) -> BranchCompletion:
    value = invocation.value
    uncertain = tuple(getattr(value, "uncertain_fields", ())) or tuple(
        getattr(value, "uncertain_symbols", ())
    )
    roles = {image.role for image in images}
    role_counts = {role: sum(image.role == role for image in images) for role in roles}
    return BranchCompletion(
        status="completed",
        result_payload=value.model_dump(mode="json"),
        uncertain_fields=uncertain,
        overall_confidence=value.overall_confidence,
        invocation=BranchInvocation(
            provider=invocation.provider,
            model=invocation.model,
            prompt_version=invocation.prompt_version,
            schema_version=invocation.schema_version,
            request_fingerprint=request_fingerprint,
            image_count=len(images),
            role_counts=role_counts,
            latency_ms=invocation.latency_ms,
            input_tokens=invocation.input_tokens,
            output_tokens=invocation.output_tokens,
            total_tokens=invocation.total_tokens,
            cached_tokens=invocation.cached_tokens,
            thought_tokens=invocation.thought_tokens,
            tool_tokens=invocation.tool_tokens,
            response_model_version=invocation.response_model_version,
        ),
    )


def _classify_provider_failure(error: Exception) -> tuple[bool, str]:
    if isinstance(error, TimeoutError):
        return True, "TIMEOUT"
    if isinstance(error, VisionProviderError):
        code = error.code.upper()
        if error.provider_http_status == 429 or (
            error.provider_http_status is not None and error.provider_http_status >= 500
        ):
            return True, code
        return code in _RETRYABLE_CODES, code
    if isinstance(error, ConnectionError | OSError):
        return True, "NETWORK"
    return False, "UNEXPECTED_PROVIDER_ERROR"


def _stable_progress_status(states: tuple[BranchState, ...]) -> str:
    by_branch = {state.branch: state for state in states}
    if any(state.status == "permanent_failed" for state in states):
        return "failed"
    label = by_branch.get(AnalysisBranch.LABEL_EXTRACTION)
    if label is not None and label.status == "not_provided":
        return "needs_better_image"
    return "processing"
