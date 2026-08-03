"""Fixed, durable native-asyncio workflow for v2 analysis branches.

The stain branch is optional and feature-gated. It runs only after the required
branches have produced a deterministic base policy, and its durable state lives
in ``analysis_branch_results`` alongside the required branches. This module is
not selected by production routes or workers until the coordinated v2 cutover.
In-memory tasks are used only while a single delivery is alive.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from random import uniform
from typing import Final, cast
from uuid import UUID

from fabricassist.application.garment_analysis.commands import AnalysisBranch
from fabricassist.application.garment_analysis.ports import (
    BranchClaim,
    BranchCompletion,
    BranchInvocation,
    BranchReanalysisRequest,
    BranchState,
    BranchStateRepository,
    FinalizationRepository,
    GarmentAnalysisRequest,
    GarmentInspectionRequest,
    GarmentVisionProvider,
    ImageAssetRepository,
    LabelExtractionRequest,
    ModelInvocation,
    ProviderImage,
    ResumeWorkflowRequest,
    StainTreatmentRequest,
    WorkflowResult,
)
from fabricassist.application.garment_analysis.queries import (
    AnalysisProgress,
    AnalysisReference,
    BranchProgress,
)
from fabricassist.application.vision import VisionProviderError
from fabricassist.domain.garment_analysis.care_policy import derive_safety_envelope
from fabricassist.domain.garment_analysis.models import (
    BranchReference,
    CarePolicy,
    GarmentInspection,
    LabelExtraction,
    MergedGarmentAssessment,
    StainTreatment,
)
from fabricassist.domain.garment_analysis.models import (
    FabricAssistAnalysisResult as DomainAnalysisResult,
)
from fabricassist.domain.garment_analysis.stain_policy import is_stain_analysis_eligible

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
    stain_analysis_enabled: bool = False

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
        finalization_repository: FinalizationRepository | None = None,
        policy: GarmentAnalysisWorkflowPolicy | None = None,
    ) -> None:
        self._branch_repository = branch_repository
        self._image_repository = image_repository
        self._provider = provider
        self._finalization_repository = finalization_repository
        self._policy = policy or GarmentAnalysisWorkflowPolicy()

    async def execute(self, request: GarmentAnalysisRequest) -> WorkflowResult:
        return await self._run_required(request.reference, stain_requested=request.stain_requested)

    async def resume(self, request: ResumeWorkflowRequest) -> WorkflowResult:
        return await self._run_required(request.reference, stain_requested=request.stain_requested)

    async def reanalyze_branch(self, request: BranchReanalysisRequest) -> WorkflowResult:
        # Reanalysis repository creation supplies a successor revision.  Thus a
        # completed source branch can never be overwritten by this invocation.
        if request.branch is AnalysisBranch.STAIN_TREATMENT:
            await self._run_optional_stain(
                request.reference,
                user_requested=True,
                base_result=None,
            )
        else:
            await self._run_branches(request.reference, (request.branch,))
        return await self._progress(request.reference)

    async def _run_required(
        self, reference: AnalysisReference, *, stain_requested: bool = False
    ) -> WorkflowResult:
        await self._run_branches(reference, _REQUIRED_BRANCHES)
        base_result: WorkflowResult | None = None
        if self._finalization_repository is not None:
            # The first deterministic finalization supplies the complete policy
            # context. A second idempotent finalization after the optional branch
            # attaches its validated projection to the same immutable result.
            base_result = await self._finalization_repository.finalize_if_ready(reference=reference)
            if base_result is None:
                return await self._progress(reference)
        optional_enabled = self._policy.stain_analysis_enabled or stain_requested
        await self._run_optional_stain(
            reference,
            user_requested=stain_requested,
            base_result=base_result,
        )
        if self._finalization_repository is not None and optional_enabled:
            finalized = await self._finalization_repository.finalize_if_ready(reference=reference)
            if finalized is not None:
                return finalized
            return await self._progress(reference)
        if base_result is not None:
            return base_result
        return await self._progress(reference)

    async def _run_optional_stain(
        self,
        reference: AnalysisReference,
        *,
        user_requested: bool,
        base_result: WorkflowResult | None,
    ) -> None:
        if not self._policy.stain_analysis_enabled:
            # Keep the default workflow shape unchanged while the v2 module is
            # inactive. An explicit on-demand request still records a skipped
            # optional branch, but never bypasses the feature flag.
            if user_requested:
                await self._branch_repository.mark_not_provided(
                    tenant_id=reference.tenant_id,
                    run_id=reference.run_id,
                    revision_id=reference.revision_id,
                    branch=AnalysisBranch.STAIN_TREATMENT,
                )
            return
        images = await self._image_repository.branch_images(
            tenant_id=reference.tenant_id,
            revision_id=reference.revision_id,
            branch=AnalysisBranch.STAIN_TREATMENT,
        )
        # Borderline imagery is useful for ordinary evidence extraction but is
        # not safe input for a treatment proposal. Unknown quality is retained
        # for older normalized-image adapters; explicit unusable/borderline
        # signals are always excluded from this safety-sensitive branch.
        stain_images = tuple(
            image for image in images if image.quality_state not in {"unusable", "borderline"}
        )
        inspection, policy, reusable_success = _stain_context(
            base_result=base_result,
            states=await self._branch_repository.branch_states(
                tenant_id=reference.tenant_id, revision_id=reference.revision_id
            ),
            revision_id=reference.revision_id,
        )
        eligible = bool(policy is not None and inspection is not None) and (
            is_stain_analysis_eligible(
                stain_image_count=len(stain_images),
                user_requested=user_requested,
                inspection=inspection,
                policy=policy,  # type: ignore[arg-type]
                feature_enabled=self._policy.stain_analysis_enabled,
                reusable_success_exists=reusable_success,
            )
        )
        if not eligible or not stain_images:
            await self._branch_repository.mark_not_provided(
                tenant_id=reference.tenant_id,
                run_id=reference.run_id,
                revision_id=reference.revision_id,
                branch=AnalysisBranch.STAIN_TREATMENT,
            )
            return
        await self._run_branches(reference, (AnalysisBranch.STAIN_TREATMENT,))

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
    ) -> (
        ModelInvocation[GarmentInspection]
        | ModelInvocation[LabelExtraction]
        | ModelInvocation[StainTreatment]
    ):
        async with asyncio.timeout(self._policy.branch_timeout_seconds):
            if branch is AnalysisBranch.GARMENT_INSPECTION:
                return await self._provider.inspect_garment(
                    GarmentInspectionRequest(images=images, attempt_number=claim.attempt_number)
                )
            if branch is AnalysisBranch.LABEL_EXTRACTION:
                return await self._provider.extract_labels(
                    LabelExtractionRequest(images=images, attempt_number=claim.attempt_number)
                )
            if branch is AnalysisBranch.STAIN_TREATMENT:
                return await self._provider.analyze_stain(
                    StainTreatmentRequest(images=images, attempt_number=claim.attempt_number)
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
                "quality_state": image.quality_state,
                "sha256": hashlib.sha256(image.jpeg_bytes).hexdigest(),
            }
            for image in images
        ],
    }
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def _success_completion(
    invocation: ModelInvocation[GarmentInspection]
    | ModelInvocation[LabelExtraction]
    | ModelInvocation[StainTreatment],
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
    if any(
        by_branch.get(branch) is not None and by_branch[branch].status == "permanent_failed"
        for branch in _REQUIRED_BRANCHES
    ):
        return "failed"
    label = by_branch.get(AnalysisBranch.LABEL_EXTRACTION)
    if label is not None and label.status == "not_provided":
        return "needs_better_image"
    return "processing"


def _stain_context(
    *,
    base_result: WorkflowResult | None,
    states: tuple[BranchState, ...],
    revision_id: UUID,
) -> tuple[GarmentInspection | None, CarePolicy | None, bool]:
    """Extract the typed base policy without trusting provider prose.

    Production finalization returns the serialized deterministic result. The
    fallback from branch payloads keeps the workflow unit-testable before the
    v2 composition root is enabled and is intentionally limited to the same
    deterministic policy function.
    """
    if base_result is not None:
        canonical = cast(Mapping[str, object], getattr(base_result, "canonical_data", {}))
        payload = canonical.get("garment_analysis_result")
        if isinstance(payload, Mapping):
            try:
                result = DomainAnalysisResult.model_validate(payload)
            except ValueError:
                pass
            else:
                stain = result.validated_stain_treatment
                return result.assessment.garment_inspection, result.care_policy, stain is not None

    by_branch = {state.branch: state for state in states}
    inspection_row = by_branch.get(AnalysisBranch.GARMENT_INSPECTION)
    label_row = by_branch.get(AnalysisBranch.LABEL_EXTRACTION)
    inspection = None
    label = None
    try:
        if inspection_row and inspection_row.result_payload:
            inspection = GarmentInspection.model_validate(inspection_row.result_payload)
        if label_row and label_row.result_payload:
            from fabricassist.domain.garment_analysis.models import LabelExtraction

            label = LabelExtraction.model_validate(label_row.result_payload)
    except ValueError:
        return None, None, False
    if inspection is None:
        return None, None, False
    assessment = MergedGarmentAssessment(
        revision_id=revision_id,
        branch_references=tuple(
            BranchReference(
                branch_name=state.branch.value,
                result_id=state.branch_result_id,
                schema_version="unknown",
            )
            for state in states
            if state.status == "completed"
        ),
        garment_inspection=inspection,
        label_extraction=label,
    )
    return inspection, derive_safety_envelope(assessment), False
