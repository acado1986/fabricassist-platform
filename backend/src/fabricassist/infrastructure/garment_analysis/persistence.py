"""SQLAlchemy persistence adapter for durable garment-analysis branch state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabricassist.application.cache import HotCache, perceptual_hash
from fabricassist.application.garment_analysis import (
    NORMALIZATION_VERSION,
    AnalysisBranch,
    AnalysisReference,
    BranchClaim,
    BranchCompletion,
    BranchState,
    EvidenceCacheRepository,
    ProviderImage,
    normalize_image_bytes,
    render_v2_answer,
)
from fabricassist.application.product_information import (
    PersistedProductLookup,
    ProductInformationError,
    ProductInformationProvider,
    lookup_and_record,
    product_lookup_from_run,
)
from fabricassist.domain.garment_analysis.models import FabricAssistAnalysisResult
from fabricassist.domain.garment_analysis.parity import (
    BarcodeEnrichment,
    ProductFactSnapshot,
    RenderedAnswerProjection,
)
from fabricassist.domain.garment_analysis.parity_cache import canonical_v2_signature
from fabricassist.domain.products import normalize_barcode
from fabricassist.infrastructure.persistence.models import (
    AiRun,
    AiRunEvent,
    AnalysisBranchResult,
    AnalysisRevision,
    CanonicalPlanCache,
    CareResult,
    EvidenceCacheEntry,
    Garment,
    GarmentIdentityCandidate,
    GarmentIdentityMatchRun,
    GarmentObservation,
    ModelRun,
    ProductLookupRun,
    RenderedAnswer,
    RenderedAnswerCache,
    Scan,
    ScanImage,
)
from fabricassist.infrastructure.telemetry import (
    GARMENT_ANALYSIS_BRANCH_LATENCY,
    GARMENT_ANALYSIS_BRANCH_TOKENS,
    GARMENT_ANALYSIS_BRANCHES,
)

_CLAIMABLE_STATUSES = ("pending", "retryable_failed")
_TERMINAL_STATUSES = {
    "completed",
    "retryable_failed",
    "permanent_failed",
    "needs_input",
    "not_provided",
}


class SqlAlchemyGarmentAnalysisRepository:
    """Persist branch claims/results without committing the caller's transaction.

    The adapter deliberately does not share sessions between asyncio tasks. Each
    task owns its own instance/session and commits its branch transition together
    with any model-run and run-event records it stages.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_branch(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
        request_fingerprint: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> BranchClaim | None:
        """Atomically create/claim a pending or expired branch, capped at two calls."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        claimed_at = now or datetime.now(UTC)
        lease_expires_at = claimed_at + timedelta(seconds=lease_seconds)

        # Tenant scope is checked before the upsert; the subsequent update also
        # includes it, so an ID from another tenant cannot be observed or claimed.
        revision = await self._session.scalar(
            select(AnalysisRevision.id).where(
                AnalysisRevision.id == revision_id,
                AnalysisRevision.tenant_id == tenant_id,
            )
        )
        if revision is None:
            return None

        await self._session.execute(
            insert(AnalysisBranchResult)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                analysis_revision_id=revision_id,
                branch_name=branch.value,
                status="pending",
                attempt_count=0,
                request_fingerprint=request_fingerprint,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    AnalysisBranchResult.analysis_revision_id,
                    AnalysisBranchResult.branch_name,
                ]
            )
        )

        claim_token = uuid4()
        stale_running = and_(
            AnalysisBranchResult.status == "running",
            AnalysisBranchResult.lease_expires_at.is_not(None),
            AnalysisBranchResult.lease_expires_at <= claimed_at,
        )
        claimable = or_(AnalysisBranchResult.status.in_(_CLAIMABLE_STATUSES), stale_running)
        row = (
            await self._session.execute(
                update(AnalysisBranchResult)
                .where(
                    AnalysisBranchResult.tenant_id == tenant_id,
                    AnalysisBranchResult.analysis_revision_id == revision_id,
                    AnalysisBranchResult.branch_name == branch.value,
                    AnalysisBranchResult.attempt_count < 2,
                    claimable,
                )
                .values(
                    status="running",
                    attempt_count=AnalysisBranchResult.attempt_count + 1,
                    claim_token=claim_token,
                    lease_expires_at=lease_expires_at,
                    request_fingerprint=request_fingerprint,
                    error_category=None,
                    completed_at=None,
                    started_at=case(
                        (AnalysisBranchResult.started_at.is_(None), claimed_at),
                        else_=AnalysisBranchResult.started_at,
                    ),
                )
                .returning(
                    AnalysisBranchResult.id,
                    AnalysisBranchResult.attempt_count,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return BranchClaim(
            branch_result_id=row.id,
            branch=branch,
            attempt_number=row.attempt_count,
            claim_token=claim_token,
        )

    async def branch_states(self, *, tenant_id: UUID, revision_id: UUID) -> tuple[BranchState, ...]:
        rows = (
            await self._session.scalars(
                select(AnalysisBranchResult)
                .where(
                    AnalysisBranchResult.tenant_id == tenant_id,
                    AnalysisBranchResult.analysis_revision_id == revision_id,
                )
                .order_by(AnalysisBranchResult.branch_name)
            )
        ).all()
        return tuple(
            BranchState(
                branch_result_id=row.id,
                branch=AnalysisBranch(row.branch_name),
                status=row.status,
                attempt_count=row.attempt_count,
                lease_expires_at=row.lease_expires_at,
                result_payload=row.result_payload,
            )
            for row in rows
        )

    async def mark_not_provided(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID | None = None,
        revision_id: UUID,
        branch: AnalysisBranch,
    ) -> None:
        """Record a routed-but-absent branch without consuming a model attempt.

        A missing label is an input condition, not a failed provider invocation;
        leaving the attempt counter at zero preserves the two-call cap for a
        successor revision that receives a new image.
        """
        revision = await self._session.scalar(
            select(AnalysisRevision.id).where(
                AnalysisRevision.id == revision_id,
                AnalysisRevision.tenant_id == tenant_id,
            )
        )
        if revision is None:
            return
        inserted = (
            await self._session.execute(
                insert(AnalysisBranchResult)
                .values(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    analysis_revision_id=revision_id,
                    branch_name=branch.value,
                    status="not_provided",
                    attempt_count=0,
                    uncertain_fields=[],
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        AnalysisBranchResult.analysis_revision_id,
                        AnalysisBranchResult.branch_name,
                    ]
                )
                .returning(AnalysisBranchResult.id)
            )
        ).scalar_one_or_none()
        if inserted is not None and run_id is not None:
            await self._append_branch_progress_event(
                tenant_id=tenant_id, run_id=run_id, branch=branch, status="not_provided"
            )

    async def complete_branch(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID | None = None,
        claim: BranchClaim,
        completion: BranchCompletion,
        now: datetime | None = None,
    ) -> bool:
        """Finish only the active lease and stage its immutable usage record.

        Returns ``False`` when another worker reclaimed the lease, preventing a
        stale external response from replacing the authoritative branch result.
        """
        if completion.status not in _TERMINAL_STATUSES:
            raise ValueError(f"Unsupported terminal branch status: {completion.status}")
        if completion.status == "completed" and completion.result_payload is None:
            raise ValueError("completed branch requires result_payload")
        completed_at = now or datetime.now(UTC)
        row = (
            await self._session.execute(
                update(AnalysisBranchResult)
                .where(
                    AnalysisBranchResult.id == claim.branch_result_id,
                    AnalysisBranchResult.tenant_id == tenant_id,
                    AnalysisBranchResult.branch_name == claim.branch.value,
                    AnalysisBranchResult.status == "running",
                    AnalysisBranchResult.claim_token == claim.claim_token,
                )
                .values(
                    status=completion.status,
                    result_payload=(
                        dict(completion.result_payload) if completion.result_payload else None
                    ),
                    uncertain_fields=list(completion.uncertain_fields),
                    overall_confidence=completion.overall_confidence,
                    error_category=completion.error_category,
                    cache_provenance=(
                        dict(completion.cache_provenance)
                        if completion.cache_provenance is not None
                        else {}
                    ),
                    provider=(
                        completion.invocation.provider
                        if completion.invocation is not None
                        else AnalysisBranchResult.provider
                    ),
                    model=(
                        completion.invocation.model
                        if completion.invocation is not None
                        else AnalysisBranchResult.model
                    ),
                    prompt_version=(
                        completion.invocation.prompt_version
                        if completion.invocation is not None
                        else AnalysisBranchResult.prompt_version
                    ),
                    schema_version=(
                        completion.invocation.schema_version
                        if completion.invocation is not None
                        else AnalysisBranchResult.schema_version
                    ),
                    claim_token=None,
                    lease_expires_at=None,
                    completed_at=completed_at,
                )
                .returning(AnalysisBranchResult.analysis_revision_id)
            )
        ).one_or_none()
        if row is None:
            return False

        if completion.invocation is not None:
            invocation = completion.invocation
            revision = await self._session.scalar(
                select(AnalysisRevision).where(
                    AnalysisRevision.id == row.analysis_revision_id,
                    AnalysisRevision.tenant_id == tenant_id,
                )
            )
            if revision is None:  # Defensive: the same transaction can be rolled back.
                raise RuntimeError("Claimed branch revision disappeared")
            self._session.add(
                ModelRun(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    scan_id=revision.scan_id,
                    analysis_revision_id=revision.id,
                    analysis_branch_result_id=claim.branch_result_id,
                    retry_number=claim.attempt_number - 1,
                    image_count=invocation.image_count,
                    role_counts=dict(invocation.role_counts),
                    operation=claim.branch.value,
                    provider=invocation.provider,
                    model=invocation.model,
                    prompt_version=invocation.prompt_version,
                    schema_version=invocation.schema_version,
                    request_fingerprint=invocation.request_fingerprint,
                    status=completion.status,
                    latency_ms=invocation.latency_ms,
                    input_tokens=invocation.input_tokens,
                    output_tokens=invocation.output_tokens,
                    total_tokens=invocation.total_tokens,
                    cached_tokens=invocation.cached_tokens,
                    thought_tokens=invocation.thought_tokens,
                    tool_tokens=invocation.tool_tokens,
                    response_model_version=invocation.response_model_version,
                    estimated_cost_usd=invocation.estimated_cost_usd,
                    error_category=completion.error_category,
                    completed_at=completed_at,
                )
            )
        if run_id is not None:
            await self._append_branch_progress_event(
                tenant_id=tenant_id,
                run_id=run_id,
                branch=claim.branch,
                status=completion.status,
            )
        await self._session.flush()
        provider = completion.invocation.provider if completion.invocation is not None else "none"
        GARMENT_ANALYSIS_BRANCHES.labels(
            branch=claim.branch.value, status=completion.status, provider=provider
        ).inc()
        if completion.invocation is not None and completion.invocation.latency_ms is not None:
            GARMENT_ANALYSIS_BRANCH_LATENCY.labels(
                branch=claim.branch.value, provider=provider
            ).observe(completion.invocation.latency_ms / 1000)
        if completion.invocation is not None and completion.invocation.total_tokens is not None:
            GARMENT_ANALYSIS_BRANCH_TOKENS.labels(
                branch=claim.branch.value, provider=provider
            ).observe(completion.invocation.total_tokens)
        return True

    async def _append_branch_progress_event(
        self, *, tenant_id: UUID, run_id: UUID, branch: AnalysisBranch, status: str
    ) -> None:
        """Append an ordered branch event inside the same transaction.

        Locking the parent run serializes the ``max(sequence) + 1`` allocation
        across the concurrently completing branch transactions.
        """
        run = await self._session.scalar(
            select(AiRun).where(AiRun.id == run_id, AiRun.tenant_id == tenant_id).with_for_update()
        )
        if run is None:
            raise RuntimeError("Claimed branch run disappeared")
        next_sequence = (
            int(
                (
                    await self._session.scalar(
                        select(func.coalesce(func.max(AiRunEvent.sequence), 0)).where(
                            AiRunEvent.run_id == run_id
                        )
                    )
                )
                or 0
            )
            + 1
        )
        self._session.add(
            AiRunEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                run_id=run_id,
                sequence=next_sequence,
                event_type="analysis.progress",
                data={"branch": branch.value, "status": status},
            )
        )


class SqlAlchemyGarmentAnalysisBranchStore:
    """Session-factory wrapper safe for concurrent asyncio workflow branches.

    Every claim, completion, and read receives a fresh session and commits its
    own short transaction.  This is the adapter a future composition root must
    pass to ``AsyncioGarmentAnalysisWorkflow``; the session-bound repository
    remains available for callers that already own one explicit transaction.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def claim_branch(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
        request_fingerprint: str,
        lease_seconds: int,
    ) -> BranchClaim | None:
        async with self._session_factory() as session, session.begin():
            return await SqlAlchemyGarmentAnalysisRepository(session).claim_branch(
                tenant_id=tenant_id,
                revision_id=revision_id,
                branch=branch,
                request_fingerprint=request_fingerprint,
                lease_seconds=lease_seconds,
            )

    async def branch_states(self, *, tenant_id: UUID, revision_id: UUID) -> tuple[BranchState, ...]:
        async with self._session_factory() as session:
            return await SqlAlchemyGarmentAnalysisRepository(session).branch_states(
                tenant_id=tenant_id, revision_id=revision_id
            )

    async def complete_branch(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        claim: BranchClaim,
        completion: BranchCompletion,
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            return await SqlAlchemyGarmentAnalysisRepository(session).complete_branch(
                tenant_id=tenant_id,
                run_id=run_id,
                claim=claim,
                completion=completion,
            )

    async def mark_not_provided(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        revision_id: UUID,
        branch: AnalysisBranch,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await SqlAlchemyGarmentAnalysisRepository(session).mark_not_provided(
                tenant_id=tenant_id,
                run_id=run_id,
                revision_id=revision_id,
                branch=branch,
            )


class SqlAlchemyGarmentAnalysisFinalizationRepository:
    """Finalize a settled v2 revision in one transaction without provider calls.

    This adapter is intentionally not composed into production until the Phase 10
    cutover.  Its idempotent `CareResult` lookup makes a duplicate finalization
    delivery return the immutable first result rather than rewriting evidence.
    """

    def __init__(
        self,
        session: AsyncSession,
        product_provider: ProductInformationProvider | None = None,
    ) -> None:
        self._session = session
        self._product_provider = product_provider

    async def finalize_if_ready(self, *, reference: AnalysisReference):
        from fabricassist.application.garment_analysis import FabricAssistAnalysisResult
        from fabricassist.domain.garment_analysis.cleaning_history import (
            CleaningOutcome,
            ServiceLifecycleKind,
        )
        from fabricassist.domain.garment_analysis.cleaning_history import (
            GarmentServiceEvent as DomainServiceEvent,
        )
        from fabricassist.domain.garment_analysis.finalization import finalize_analysis
        from fabricassist.domain.garment_analysis.models import (
            BranchReference,
            ConflictSeverity,
            CorrectionConfirmation,
            CorrectionSource,
            GarmentInspection,
            LabelExtraction,
            MergedGarmentAssessment,
            StainTreatment,
        )
        from fabricassist.domain.garment_analysis.models import (
            EvidenceCorrection as DomainEvidenceCorrection,
        )
        from fabricassist.domain.garment_analysis.stain_policy import validate_stain_treatment
        from fabricassist.infrastructure.persistence.models import (
            EvidenceConflictRecord,
            EvidenceCorrection,
            EvidenceDossier,
            GarmentServiceEvent,
            ProposedPlan,
            ValidationReport,
        )

        revision = await self._session.scalar(
            select(AnalysisRevision)
            .where(
                AnalysisRevision.id == reference.revision_id,
                AnalysisRevision.tenant_id == reference.tenant_id,
            )
            .with_for_update()
        )
        if revision is None:
            return None
        existing = await self._session.scalar(
            select(CareResult).where(
                CareResult.tenant_id == reference.tenant_id,
                CareResult.analysis_revision_id == revision.id,
            )
        )
        if existing is not None:
            # The workflow may have persisted the deterministic base result
            # before the optional stain call. Attach a completed stain branch
            # exactly once, while retaining the base care-result status.
            stain_row = await self._session.scalar(
                select(AnalysisBranchResult).where(
                    AnalysisBranchResult.tenant_id == reference.tenant_id,
                    AnalysisBranchResult.analysis_revision_id == revision.id,
                    AnalysisBranchResult.branch_name == AnalysisBranch.STAIN_TREATMENT.value,
                    AnalysisBranchResult.status == "completed",
                )
            )
            canonical_payload = existing.canonical_data.get("garment_analysis_result")
            if stain_row is not None and isinstance(canonical_payload, dict):
                from fabricassist.domain.garment_analysis.models import (
                    FabricAssistAnalysisResult as DomainAnalysisResult,
                )

                try:
                    domain_result = DomainAnalysisResult.model_validate(canonical_payload)
                    treatment = StainTreatment.model_validate(stain_row.result_payload)
                except ValueError:
                    # A malformed optional branch must never make an existing
                    # safe base result unavailable; the branch remains audit data.
                    pass
                else:
                    if domain_result.validated_stain_treatment is None:
                        validated = validate_stain_treatment(domain_result.care_policy, treatment)
                        updated = domain_result.model_copy(
                            update={"validated_stain_treatment": validated}
                        )
                        existing.canonical_data = {
                            "garment_analysis_result": updated.model_dump(mode="json")
                        }
                        proposal = await self._session.get(ProposedPlan, existing.proposed_plan_id)
                        if proposal is not None:
                            proposal.payload = {
                                **proposal.payload,
                                "stain_treatment": treatment.model_dump(mode="json"),
                                "validated_stain_treatment": validated.model_dump(mode="json"),
                            }
                        report = await self._session.get(
                            ValidationReport, existing.validation_report_id
                        )
                        if report is not None:
                            report.payload = {
                                **report.payload,
                                "stain": validated.model_dump(mode="json"),
                            }
            await self._publish_active_result(
                revision=revision, care_result=existing, outcome=existing.status
            )
            return FabricAssistAnalysisResult(
                reference=reference,
                status=existing.status,
                canonical_data=existing.canonical_data,
            )
        rows = list(
            (
                await self._session.scalars(
                    select(AnalysisBranchResult).where(
                        AnalysisBranchResult.tenant_id == reference.tenant_id,
                        AnalysisBranchResult.analysis_revision_id == revision.id,
                    )
                )
            ).all()
        )
        branches = {row.branch_name: row for row in rows}
        required = {AnalysisBranch.GARMENT_INSPECTION.value, AnalysisBranch.LABEL_EXTRACTION.value}
        if not required.issubset(branches) or any(
            branches[name].status in {"pending", "running", "retryable_failed"} for name in required
        ):
            return None
        label_row = branches[AnalysisBranch.LABEL_EXTRACTION.value]
        if label_row.status == "permanent_failed":
            revision.status = "failed"
            revision.finalized_at = datetime.now(UTC)
            scan = await self._session.get(Scan, revision.scan_id, with_for_update=True)
            if scan is not None:
                scan.status = "failed"
                scan.analysis_stage = "failed"
                scan.analysis_error_code = "LABEL_EXTRACTION_FAILED"
                scan.progress_percent = 100
            return FabricAssistAnalysisResult(reference=reference, status="failed")
        inspection_row = branches[AnalysisBranch.GARMENT_INSPECTION.value]
        inspection = (
            GarmentInspection.model_validate(inspection_row.result_payload)
            if inspection_row.status == "completed" and inspection_row.result_payload is not None
            else None
        )
        label = (
            LabelExtraction.model_validate(label_row.result_payload)
            if label_row.status == "completed" and label_row.result_payload is not None
            else None
        )
        predecessor_assessment = None
        if revision.supersedes_revision_id is not None:
            predecessor_dossier = await self._session.scalar(
                select(EvidenceDossier).where(
                    EvidenceDossier.tenant_id == reference.tenant_id,
                    EvidenceDossier.analysis_revision_id == revision.supersedes_revision_id,
                )
            )
            if predecessor_dossier is not None:
                try:
                    predecessor_assessment = MergedGarmentAssessment.model_validate(
                        predecessor_dossier.payload
                    )
                except ValueError:
                    predecessor_assessment = None
        # A successor carrying only a new stain/damage photo reuses stable v2
        # inspection/label facts, while a newly supplied branch supersedes them.
        if inspection is None and predecessor_assessment is not None:
            inspection = predecessor_assessment.garment_inspection
        if label is None and predecessor_assessment is not None:
            label = predecessor_assessment.label_extraction
        product_lookup = await self._lookup_product(
            scan_id=revision.scan_id, revision_id=revision.id, branches=branches
        )
        history: tuple[DomainServiceEvent, ...] = ()
        if revision.garment_id is not None:
            event_rows = list(
                (
                    await self._session.scalars(
                        select(GarmentServiceEvent).where(
                            GarmentServiceEvent.tenant_id == reference.tenant_id,
                            GarmentServiceEvent.garment_id == revision.garment_id,
                        )
                    )
                ).all()
            )
            history = tuple(
                DomainServiceEvent(
                    event_id=row.id,
                    garment_id=row.garment_id,
                    exact_garment_confirmed=row.exact_garment_confirmed,
                    lifecycle_kind=ServiceLifecycleKind(row.kind),
                    outcome=CleaningOutcome(row.outcome),
                    method=row.method,
                    water_temperature_c=row.water_temperature_c,
                    cycle=row.cycle,
                    detergent_category=row.detergent_category,
                    detergent_text=row.detergent_text,
                    stain_products=tuple(row.stain_products),
                    drying_method=row.drying_method,
                    ironing_method=row.ironing_method,
                    observed_effects=tuple(row.observed_effects),
                    confirmed_by=row.confirmed_by,
                    occurred_at=row.occurred_at,
                    detail_schema_version=row.detail_schema_version,
                    detail_snapshot=row.detail_snapshot,
                    invalidated=row.invalidated,
                    superseded_by_event_id=row.superseded_by_event_id,
                )
                for row in event_rows
            )
        correction_revision_ids = [revision.id]
        if revision.supersedes_revision_id is not None:
            correction_revision_ids.append(revision.supersedes_revision_id)
        correction_rows = list(
            (
                await self._session.scalars(
                    select(EvidenceCorrection)
                    .where(
                        EvidenceCorrection.tenant_id == reference.tenant_id,
                        EvidenceCorrection.corrected_revision_id.in_(correction_revision_ids),
                        EvidenceCorrection.confirmation == "accepted",
                        EvidenceCorrection.field_path != "unknown",
                    )
                    .order_by(EvidenceCorrection.created_at.asc())
                )
            ).all()
        )
        corrections = tuple(
            DomainEvidenceCorrection(
                correction_id=row.id,
                revision_id=revision.id,
                field_path=row.field_path,
                previous_value=row.previous_value,
                corrected_value=row.corrected_value,
                source_image_id=row.source_image_id,
                source=CorrectionSource(row.source),
                reason=row.reason,
                confirmation=CorrectionConfirmation(row.confirmation),
                supersedes_correction_id=row.supersedes_correction_id,
            )
            for row in correction_rows
        )
        result = finalize_analysis(
            revision_id=revision.id,
            branch_references=tuple(
                BranchReference(
                    branch_name=row.branch_name,
                    result_id=row.id,
                    schema_version=row.schema_version or "unknown",
                )
                for row in rows
                if row.status == "completed" and row.result_payload is not None
            ),
            garment_inspection=inspection,
            label_extraction=label,
            history=history,
            corrections=corrections,
            versions={
                "module": revision.module_version,
                "workflow": revision.workflow_version,
                "confidence_policy": revision.confidence_policy_version,
                "retry_policy": revision.retry_policy_version,
            },
        )
        cache_provenance = {
            row.branch_name: row.cache_provenance for row in rows if row.cache_provenance
        }
        if cache_provenance:
            result = result.model_copy(
                update={
                    "versions": {
                        **result.versions,
                        "cache_provenance": json.dumps(
                            cache_provenance, sort_keys=True, separators=(",", ":")
                        ),
                    }
                }
            )
        if product_lookup is not None:
            product_facts = None
            if product_lookup.product is not None:
                try:
                    product_facts = ProductFactSnapshot.model_validate(product_lookup.product)
                except ValueError:
                    product_facts = None
            result = result.model_copy(
                update={
                    "assessment": result.assessment.model_copy(
                        update={
                            "product_barcode": product_lookup.barcode,
                            "product_lookup_status": product_lookup.status,
                            "product_source": product_lookup.source_name,
                            "product_facts": product_facts,
                        }
                    ),
                    "versions": {
                        **result.versions,
                        "product_lookup": "product-lookup-v2",
                    },
                }
            )
        stain_row = branches.get(AnalysisBranch.STAIN_TREATMENT.value)
        stain_treatment = None
        if stain_row is not None and stain_row.status == "completed" and stain_row.result_payload:
            try:
                stain_treatment = StainTreatment.model_validate(stain_row.result_payload)
            except ValueError:
                stain_treatment = None
        if stain_treatment is not None:
            result = result.model_copy(
                update={
                    "validated_stain_treatment": validate_stain_treatment(
                        result.care_policy, stain_treatment
                    )
                }
            )
        dossier = EvidenceDossier(
            id=uuid4(),
            tenant_id=reference.tenant_id,
            analysis_revision_id=revision.id,
            payload=result.assessment.model_dump(mode="json"),
        )
        proposal = ProposedPlan(
            id=uuid4(),
            tenant_id=reference.tenant_id,
            analysis_revision_id=revision.id,
            retry_number=0,
            payload={
                "schema_version": "deterministic-care-proposal-v2",
                "care_policy": result.care_policy.model_dump(mode="json"),
                "recommendation": result.recommendation.model_dump(mode="json"),
                **(
                    {
                        "stain_treatment": stain_treatment.model_dump(mode="json"),
                        "validated_stain_treatment": result.validated_stain_treatment.model_dump(
                            mode="json"
                        ),
                    }
                    if stain_treatment is not None and result.validated_stain_treatment is not None
                    else {}
                ),
            },
        )
        self._session.add_all((dossier, proposal))
        await self._session.flush()
        report = ValidationReport(
            id=uuid4(),
            tenant_id=reference.tenant_id,
            proposed_plan_id=proposal.id,
            payload={
                "schema_version": "deterministic-care-validation-v2",
                "outcome": result.care_policy.outcome.value,
                "warnings": list(result.care_policy.warnings),
                "conflicts": [
                    conflict.model_dump(mode="json") for conflict in result.care_policy.conflicts
                ],
                "policy_version": result.care_policy.care_policy_version,
                "policy_checksum": result.care_policy.policy_checksum,
                **(
                    {"stain": result.validated_stain_treatment.model_dump(mode="json")}
                    if result.validated_stain_treatment is not None
                    else {}
                ),
            },
        )
        self._session.add(report)
        await self._session.flush()
        canonical = result.model_dump(mode="json")
        care_result = CareResult(
            id=uuid4(),
            tenant_id=reference.tenant_id,
            analysis_revision_id=revision.id,
            dossier_id=dossier.id,
            proposed_plan_id=proposal.id,
            validation_report_id=report.id,
            status=result.care_policy.outcome.value,
            canonical_data={"garment_analysis_result": canonical},
        )
        self._session.add(care_result)
        await self._persist_v2_projections(
            revision=revision,
            care_result=care_result,
            result=result,
            product_lookup=product_lookup,
        )
        for conflict in result.assessment.conflicts:
            self._session.add(
                EvidenceConflictRecord(
                    id=conflict.conflict_id,
                    tenant_id=reference.tenant_id,
                    analysis_revision_id=revision.id,
                    field_path=conflict.field_path,
                    values=list(conflict.values),
                    evidence=[item.model_dump(mode="json") for item in conflict.evidence],
                    selected_value=conflict.selected_value,
                    resolution_code=conflict.resolution_code,
                    explanation_key=conflict.explanation_key,
                    safety_critical=conflict.severity is ConflictSeverity.SAFETY,
                )
            )
        revision.status = result.care_policy.outcome.value
        revision.merged_schema_version = result.assessment.schema_version
        revision.care_policy_version = result.care_policy.care_policy_version
        revision.finalized_at = datetime.now(UTC)
        await self._publish_active_result(
            revision=revision,
            care_result=care_result,
            outcome=result.care_policy.outcome.value,
        )
        return FabricAssistAnalysisResult(
            reference=reference,
            status=care_result.status,
            canonical_data=care_result.canonical_data,
        )

    async def _persist_v2_projections(
        self,
        *,
        revision: AnalysisRevision,
        care_result: CareResult,
        result: FabricAssistAnalysisResult,
        product_lookup: PersistedProductLookup | None,
    ) -> None:
        """Write append-only garment memory and deterministic answer projections."""
        product_fingerprint = None
        if product_lookup is not None and product_lookup.product is not None:
            product_fingerprint = hashlib.sha256(
                json.dumps(product_lookup.product, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        signature = canonical_v2_signature(result, product_fingerprint=product_fingerprint)
        existing_signature = await self._session.scalar(
            select(CanonicalPlanCache).where(
                CanonicalPlanCache.tenant_id == revision.tenant_id,
                CanonicalPlanCache.signature == signature,
            )
        )
        if existing_signature is None:
            self._session.add(
                CanonicalPlanCache(
                    id=uuid4(),
                    tenant_id=revision.tenant_id,
                    signature=signature,
                    care_result_id=care_result.id,
                    evidence_schema_version=result.assessment.schema_version,
                    proposal_schema_version="deterministic-care-proposal-v2",
                    validator_version=result.care_policy.care_policy_version,
                    product_fingerprint=product_fingerprint,
                )
            )
        else:
            existing_signature.reuse_count += 1
            existing_signature.last_reused_at = datetime.now(UTC)
        for language in ("en", "es"):
            template_version = "care-rendering-v2"
            rendered_cache = await self._session.scalar(
                select(RenderedAnswerCache)
                .where(
                    RenderedAnswerCache.tenant_id == revision.tenant_id,
                    RenderedAnswerCache.canonical_signature == signature,
                    RenderedAnswerCache.language == language,
                    RenderedAnswerCache.template_version == template_version,
                )
                .with_for_update()
            )
            if rendered_cache is None:
                projection = render_v2_answer(
                    result_id=care_result.id,
                    result=result,
                    language=language,
                    template_version=template_version,
                )
                cache_answer = projection.model_dump(mode="json")
                self._session.add(
                    RenderedAnswerCache(
                        id=uuid4(),
                        tenant_id=revision.tenant_id,
                        canonical_signature=signature,
                        language=language,
                        template_version=projection.template_version,
                        answer=cache_answer,
                        source_care_result_id=care_result.id,
                    )
                )
            else:
                # Rendering is deterministic and the signature includes the
                # safety facts and product fingerprint. Reuse only an exact
                # template-version match and rebind the projection to this
                # immutable result row for correct provenance.
                projection = RenderedAnswerProjection.model_validate(
                    {**rendered_cache.answer, "result_id": str(care_result.id)}
                )
                rendered_cache.reuse_count += 1
                rendered_cache.last_reused_at = datetime.now(UTC)
            self._session.add(
                RenderedAnswer(
                    id=uuid4(),
                    tenant_id=revision.tenant_id,
                    care_result_id=care_result.id,
                    language=language,
                    template_version=projection.template_version,
                    answer=projection.model_dump(mode="json"),
                )
            )
        if revision.garment_id is None:
            return
        observation_specs: list[
            tuple[str, str, dict[str, object], float | None, str, tuple[UUID, ...]]
        ] = []
        inspection = result.assessment.garment_inspection
        if inspection is not None:
            category_evidence_ids = tuple(
                image_id
                for evidence in inspection.field_evidence
                if evidence.field_path in {"category", "garment.category"}
                for image_id in evidence.source_image_ids
            )
            observation_specs.append(
                (
                    "garment_category",
                    "stable",
                    {"category": inspection.category, "subtype": inspection.subtype},
                    inspection.overall_confidence,
                    "visual_inference",
                    category_evidence_ids,
                )
            )
            for issue in inspection.issues:
                observation_specs.append(
                    (
                        f"issue:{issue.issue_id}",
                        "condition",
                        issue.model_dump(mode="json"),
                        issue.confidence,
                        "visual_inference",
                        issue.source_image_ids,
                    )
                )
        label = result.assessment.label_extraction
        if label is not None:
            for index, material in enumerate(label.materials):
                observation_specs.append(
                    (
                        f"material:{index}:{material.material}",
                        "stable",
                        material.model_dump(mode="json"),
                        material.confidence,
                        "photographed_label",
                        material.source_image_ids,
                    )
                )
        for action in (
            *result.care_policy.allowed_actions,
            *result.care_policy.prohibited_actions,
            *result.care_policy.unknown_actions,
        ):
            observation_specs.append(
                (
                    f"care:{action.code}",
                    "stable",
                    action.model_dump(mode="json"),
                    None,
                    "photographed_label" if label is not None else "inferred",
                    tuple(
                        image_id
                        for evidence in (label.field_evidence if label is not None else ())
                        if evidence.field_path in action.evidence_paths
                        for image_id in evidence.source_image_ids
                    ),
                )
            )
        for (
            projection_key,
            stability,
            value,
            confidence,
            authority,
            evidence_ids,
        ) in observation_specs:
            prior = await self._session.scalar(
                select(GarmentObservation)
                .where(
                    GarmentObservation.tenant_id == revision.tenant_id,
                    GarmentObservation.garment_id == revision.garment_id,
                    GarmentObservation.projection_key == projection_key,
                    GarmentObservation.analysis_revision_id != revision.id,
                )
                .order_by(GarmentObservation.created_at.desc())
                .limit(1)
            )
            duplicate = await self._session.scalar(
                select(GarmentObservation.id).where(
                    GarmentObservation.analysis_revision_id == revision.id,
                    GarmentObservation.projection_key == projection_key,
                )
            )
            if duplicate is not None:
                continue
            self._session.add(
                GarmentObservation(
                    id=uuid4(),
                    tenant_id=revision.tenant_id,
                    garment_id=revision.garment_id,
                    analysis_revision_id=revision.id,
                    observation_type=projection_key.split(":", 1)[0],
                    projection_key=projection_key,
                    stability=stability,
                    authority=authority,
                    evidence_ids=list(evidence_ids),
                    value=value,
                    confidence=confidence,
                    supersedes_observation_id=prior.id if prior is not None else None,
                )
            )

    async def _lookup_product(
        self,
        *,
        scan_id: UUID,
        revision_id: UUID,
        branches: dict[str, AnalysisBranchResult],
    ) -> PersistedProductLookup | None:
        """Enrich from one validated barcode without affecting care policy."""
        scan = await self._session.get(Scan, scan_id, with_for_update=True)
        if scan is None:
            return None
        row = branches.get(AnalysisBranch.BARCODE_ENRICHMENT.value)
        barcode = None
        if row is not None and row.status == "completed" and row.result_payload:
            try:
                enrichment = BarcodeEnrichment.model_validate(row.result_payload)
            except ValueError:
                enrichment = None
            if enrichment is not None:
                for candidate in enrichment.candidates:
                    if candidate.status.value != "valid":
                        continue
                    try:
                        barcode = normalize_barcode(
                            candidate.normalized_value or candidate.raw_value
                        )
                    except ValueError:
                        continue
                    break
        # The upload flow also supports a user-entered barcode before the run.
        # Preserve that v1 capability in the v2 result without requiring an
        # optional barcode-label branch.
        if barcode is None:
            manual_run = await self._session.scalar(
                select(ProductLookupRun)
                .where(
                    ProductLookupRun.tenant_id == scan.tenant_id,
                    ProductLookupRun.scan_id == scan.id,
                    ProductLookupRun.invalidated_at.is_(None),
                    ProductLookupRun.status.in_(("exact", "probable")),
                )
                .order_by(ProductLookupRun.created_at.desc())
                .limit(1)
            )
            if manual_run is not None:
                manual_run.analysis_revision_id = revision_id
                return product_lookup_from_run(manual_run)
        if barcode is None or self._product_provider is None:
            return None
        try:
            lookup = await lookup_and_record(
                session=self._session,
                scan=scan,
                barcode=barcode,
                provider=self._product_provider,
            )
            run = await self._session.scalar(
                select(ProductLookupRun)
                .where(
                    ProductLookupRun.scan_id == scan.id,
                    ProductLookupRun.barcode == barcode,
                    ProductLookupRun.tenant_id == scan.tenant_id,
                )
                .order_by(ProductLookupRun.created_at.desc())
                .limit(1)
            )
            if run is not None:
                run.analysis_revision_id = revision_id
            return lookup
        except ProductInformationError as error:
            # Enrichment is an optional branch. Persist an auditable outage
            # without turning a safe label result into a failed analysis.
            run = ProductLookupRun(
                id=uuid4(),
                tenant_id=scan.tenant_id,
                scan_id=scan.id,
                barcode=barcode,
                provider=type(self._product_provider).__name__,
                status="outage",
                schema_version="product-lookup-v2",
                analysis_revision_id=revision_id,
                safe_snapshot={"error_code": error.code},
                validated_snapshot={},
            )
            self._session.add(run)
            await self._session.flush()
            return PersistedProductLookup(
                barcode=barcode,
                status="outage",
                provider=type(self._product_provider).__name__,
                source_name=None,
                source_reference=None,
                license_name=None,
                retrieved_at=run.created_at,
                product=None,
            )

    async def _publish_active_result(
        self,
        *,
        revision: AnalysisRevision,
        care_result: CareResult,
        outcome: str,
    ) -> None:
        """Advance only the v2 active pointers after canonical persistence.

        The result row and revision are locked by ``finalize_if_ready``; the scan
        lock makes duplicate finalization deliveries deterministic and keeps the
        GraphQL projection from observing a legacy rendered answer.
        """
        scan = await self._session.get(Scan, revision.scan_id, with_for_update=True)
        if scan is None:
            return
        await self._record_exact_image_candidates(scan)
        scan.active_analysis_revision_id = revision.id
        scan.active_result_id = care_result.id
        scan.analysis_stage = "completed"
        scan.progress_percent = 100
        scan.analysis_error_code = None
        scan.status = {
            "passed": "completed",
            "passed_with_warnings": "completed",
            "needs_better_image": "needs_better_image",
            "needs_review": "needs_review",
            "blocked": "needs_review",
        }.get(outcome, "failed")
        if scan.status != "completed":
            scan.analysis_error_code = outcome.upper()
        if revision.garment_id is not None:
            garment = await self._session.get(Garment, revision.garment_id, with_for_update=True)
            if garment is not None:
                garment.active_analysis_revision_id = revision.id
                garment.active_result_id = care_result.id

    async def _record_exact_image_candidates(self, scan: Scan) -> None:
        """Record probable physical-garment matches without auto-linking."""
        current_images = list(
            (
                await self._session.execute(
                    select(ScanImage.normalized_sha256, ScanImage.role).where(
                        ScanImage.scan_id == scan.id,
                        ScanImage.normalized_sha256.is_not(None),
                        ScanImage.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        if not current_images:
            return
        exact_conditions = [
            (ScanImage.normalized_sha256 == normalized, ScanImage.role == role)
            for normalized, role in current_images
        ]
        exact_candidates = list(
            (
                await self._session.scalars(
                    select(Scan.garment_id)
                    .join(ScanImage, ScanImage.scan_id == Scan.id)
                    .where(
                        Scan.tenant_id == scan.tenant_id,
                        Scan.user_id == scan.user_id,
                        Scan.id != scan.id,
                        Scan.garment_id.is_not(None),
                        ScanImage.deleted_at.is_(None),
                        or_(*[and_(sha, role) for sha, role in exact_conditions]),
                    )
                    .distinct()
                )
            ).all()
        )
        product_runs = list(
            (
                await self._session.scalars(
                    select(ProductLookupRun).where(
                        ProductLookupRun.tenant_id == scan.tenant_id,
                        ProductLookupRun.scan_id == scan.id,
                        ProductLookupRun.status.in_(("exact", "probable")),
                        ProductLookupRun.invalidated_at.is_(None),
                    )
                )
            ).all()
        )
        same_product_ids: list[UUID] = []
        for run in product_runs:
            same_product_ids.extend(
                garment_id
                for garment_id in (
                    await self._session.scalars(
                        select(Scan.garment_id)
                        .join(ProductLookupRun, ProductLookupRun.scan_id == Scan.id)
                        .where(
                            Scan.tenant_id == scan.tenant_id,
                            Scan.user_id == scan.user_id,
                            Scan.id != scan.id,
                            Scan.garment_id.is_not(None),
                            ProductLookupRun.barcode == run.barcode,
                            ProductLookupRun.status.in_(("exact", "probable")),
                            ProductLookupRun.invalidated_at.is_(None),
                        )
                        .distinct()
                    )
                ).all()
                if garment_id is not None
            )
        visual_hashes = [
            value
            for value in (
                await self._session.scalars(
                    select(ScanImage.perceptual_hash).where(
                        ScanImage.scan_id == scan.id,
                        ScanImage.role == "garment_overview",
                        ScanImage.perceptual_hash.is_not(None),
                        ScanImage.deleted_at.is_(None),
                    )
                )
            ).all()
            if value is not None
        ]
        visual_ids: list[UUID] = []
        if visual_hashes:
            candidate_hashes = list(
                (
                    await self._session.execute(
                        select(Scan.garment_id, ScanImage.perceptual_hash)
                        .join(ScanImage, ScanImage.scan_id == Scan.id)
                        .where(
                            Scan.tenant_id == scan.tenant_id,
                            Scan.user_id == scan.user_id,
                            Scan.id != scan.id,
                            Scan.garment_id.is_not(None),
                            ScanImage.role == "garment_overview",
                            ScanImage.perceptual_hash.is_not(None),
                            ScanImage.deleted_at.is_(None),
                        )
                    )
                ).all()
            )
            visual_ids = list(
                {
                    garment_id
                    for garment_id, candidate_hash in candidate_hashes
                    if garment_id is not None
                    and candidate_hash is not None
                    and any(
                        _perceptual_distance(current_hash, candidate_hash) <= 6
                        for current_hash in visual_hashes
                    )
                }
            )
        candidates_by_garment: dict[UUID, str] = {
            garment_id: "probable_instance" for garment_id in exact_candidates if garment_id
        }
        for garment_id in same_product_ids:
            if garment_id and garment_id not in candidates_by_garment:
                candidates_by_garment[garment_id] = "same_product"
        for garment_id in visual_ids:
            if garment_id not in candidates_by_garment:
                candidates_by_garment[garment_id] = "visual_candidate"
        if not candidates_by_garment:
            return
        match_run = await self._session.scalar(
            select(GarmentIdentityMatchRun).where(
                GarmentIdentityMatchRun.scan_id == scan.id,
                GarmentIdentityMatchRun.tenant_id == scan.tenant_id,
            )
        )
        if match_run is None:
            match_run = GarmentIdentityMatchRun(
                id=uuid4(),
                tenant_id=scan.tenant_id,
                scan_id=scan.id,
                classification=(
                    "probable_instance"
                    if "probable_instance" in candidates_by_garment.values()
                    else "same_product"
                    if "same_product" in candidates_by_garment.values()
                    else "visual_candidate"
                ),
                reasons={"sources": sorted({*candidates_by_garment.values()})},
            )
            self._session.add(match_run)
            await self._session.flush()
        for garment_id, classification in candidates_by_garment.items():
            if garment_id == scan.garment_id:
                continue
            exists = await self._session.scalar(
                select(GarmentIdentityCandidate.id).where(
                    GarmentIdentityCandidate.match_run_id == match_run.id,
                    GarmentIdentityCandidate.garment_id == garment_id,
                )
            )
            if exists is None:
                self._session.add(
                    GarmentIdentityCandidate(
                        id=uuid4(),
                        tenant_id=scan.tenant_id,
                        match_run_id=match_run.id,
                        garment_id=garment_id,
                        classification=classification,
                        reasons={"source": "normalized_image_sha256"}
                        if classification == "probable_instance"
                        else {"source": "trusted_product_barcode"}
                        if classification == "same_product"
                        else {"source": "perceptual_hash_candidate", "maximum_distance": 6},
                    )
                )


def _perceptual_distance(left: str, right: str) -> int:
    """Hamming distance for candidate discovery only; never a reuse or link key."""
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 64


class SqlAlchemyGarmentAnalysisFinalizationStore:
    """Transaction-per-call wrapper used by parallel/re-delivered workflows."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        product_provider: ProductInformationProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._product_provider = product_provider

    async def finalize_if_ready(self, *, reference: AnalysisReference):
        async with self._session_factory() as session, session.begin():
            return await SqlAlchemyGarmentAnalysisFinalizationRepository(
                session, self._product_provider
            ).finalize_if_ready(reference=reference)


class SqlAlchemyV2EvidenceCacheRepository(EvidenceCacheRepository):
    """Exact normalized-image cache adapter with PostgreSQL as authority."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._hot_cache: HotCache | None = None
        self._hot_cache_ttl_seconds = 86_400

    def with_hot_cache(
        self, cache: HotCache, *, ttl_seconds: int
    ) -> SqlAlchemyV2EvidenceCacheRepository:
        self._hot_cache = cache
        self._hot_cache_ttl_seconds = ttl_seconds
        return self

    @staticmethod
    def _cache_sha(images: tuple[ProviderImage, ...]) -> str:
        hashes = [normalize_image_bytes(image.jpeg_bytes).sha256 for image in images]
        if len(hashes) == 1:
            return hashes[0]
        return hashlib.sha256("|".join(hashes).encode()).hexdigest()

    @classmethod
    def _hot_key(
        cls,
        *,
        tenant_id: UUID,
        branch: AnalysisBranch,
        images: tuple[ProviderImage, ...],
        provider: str,
        model: str,
        prompt_version: str,
        schema_version: str,
    ) -> str:
        return ":".join(
            (
                "fabricassist",
                "garment-analysis-v2",
                "evidence",
                str(tenant_id),
                branch.value,
                cls._cache_sha(images),
                NORMALIZATION_VERSION,
                provider,
                model,
                prompt_version,
                schema_version,
            )
        )

    async def get_branch_result(
        self,
        *,
        tenant_id: UUID,
        branch: AnalysisBranch,
        images: tuple[ProviderImage, ...],
        provider: str,
        model: str,
        prompt_version: str,
        schema_version: str,
    ) -> dict[str, object] | None:
        hot_key = self._hot_key(
            tenant_id=tenant_id,
            branch=branch,
            images=images,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            schema_version=schema_version,
        )
        cache_sha = self._cache_sha(images)
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(EvidenceCacheEntry)
                .where(
                    EvidenceCacheEntry.tenant_id == tenant_id,
                    EvidenceCacheEntry.normalized_sha256 == cache_sha,
                    EvidenceCacheEntry.role == branch.value,
                    EvidenceCacheEntry.normalization_version == NORMALIZATION_VERSION,
                    EvidenceCacheEntry.schema_version == schema_version,
                    EvidenceCacheEntry.prompt_version == prompt_version,
                    EvidenceCacheEntry.provider == provider,
                    EvidenceCacheEntry.model == model,
                )
                .with_for_update()
            )
            if row is None:
                return None
            row.reuse_count += 1
            row.last_reused_at = datetime.now(UTC)
            if self._hot_cache is not None:
                hot_payload = await self._hot_cache.get_json(hot_key)
                if hot_payload is not None:
                    return {"_cache_source": "valkey_hot", **hot_payload}
            payload = dict(row.delta_payload)
            if self._hot_cache is not None:
                await self._hot_cache.set_json(
                    hot_key, payload, ttl_seconds=self._hot_cache_ttl_seconds
                )
            return {"_cache_source": "postgres_exact", **payload}

    async def store_branch_result(
        self,
        *,
        tenant_id: UUID,
        branch: AnalysisBranch,
        images: tuple[ProviderImage, ...],
        provider: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        payload: Mapping[str, object],
    ) -> None:
        cache_sha = self._cache_sha(images)
        hot_key = self._hot_key(
            tenant_id=tenant_id,
            branch=branch,
            images=images,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            schema_version=schema_version,
        )
        from fabricassist.application.vision import NormalizedImage
        from fabricassist.domain.evidence import ImageRole

        normalized = normalize_image_bytes(images[0].jpeg_bytes)
        image = NormalizedImage(
            image_id=images[0].image_id,
            jpeg_bytes=normalized.jpeg_bytes,
            sha256=normalized.sha256,
            width=normalized.width,
            height=normalized.height,
            role=ImageRole.BARCODE_BRAND_LABEL
            if branch is AnalysisBranch.BARCODE_ENRICHMENT
            else ImageRole.OTHER,
        )
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(EvidenceCacheEntry).where(
                    EvidenceCacheEntry.tenant_id == tenant_id,
                    EvidenceCacheEntry.normalized_sha256 == cache_sha,
                    EvidenceCacheEntry.role == branch.value,
                    EvidenceCacheEntry.normalization_version == NORMALIZATION_VERSION,
                    EvidenceCacheEntry.schema_version == schema_version,
                    EvidenceCacheEntry.prompt_version == prompt_version,
                    EvidenceCacheEntry.provider == provider,
                    EvidenceCacheEntry.model == model,
                )
            )
            if existing is not None:
                return
            session.add(
                EvidenceCacheEntry(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    normalized_sha256=cache_sha,
                    perceptual_hash=perceptual_hash(image),
                    role=branch.value,
                    normalization_version=NORMALIZATION_VERSION,
                    schema_version=schema_version,
                    prompt_version=prompt_version,
                    provider=provider,
                    model=model,
                    delta_payload=dict(payload),
                    source_image_id=images[0].image_id,
                )
            )
            scan_image = await session.get(ScanImage, images[0].image_id)
            if scan_image is not None:
                scan_image.perceptual_hash = perceptual_hash(image)
        if self._hot_cache is not None:
            await self._hot_cache.set_json(
                hot_key, dict(payload), ttl_seconds=self._hot_cache_ttl_seconds
            )
