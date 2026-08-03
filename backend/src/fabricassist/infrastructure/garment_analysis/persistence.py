"""SQLAlchemy persistence adapter for durable garment-analysis branch state."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabricassist.application.garment_analysis import (
    AnalysisBranch,
    AnalysisReference,
    BranchClaim,
    BranchCompletion,
    BranchState,
)
from fabricassist.infrastructure.persistence.models import (
    AiRun,
    AiRunEvent,
    AnalysisBranchResult,
    AnalysisRevision,
    ModelRun,
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

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
            StainTreatment,
        )
        from fabricassist.domain.garment_analysis.models import (
            EvidenceCorrection as DomainEvidenceCorrection,
        )
        from fabricassist.domain.garment_analysis.stain_policy import validate_stain_treatment
        from fabricassist.infrastructure.persistence.models import (
            CareResult,
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
        correction_rows = list(
            (
                await self._session.scalars(
                    select(EvidenceCorrection).where(
                        EvidenceCorrection.tenant_id == reference.tenant_id,
                        EvidenceCorrection.corrected_revision_id == revision.id,
                        EvidenceCorrection.confirmation == "accepted",
                        EvidenceCorrection.field_path != "unknown",
                    )
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
        return FabricAssistAnalysisResult(
            reference=reference,
            status=care_result.status,
            canonical_data=care_result.canonical_data,
        )


class SqlAlchemyGarmentAnalysisFinalizationStore:
    """Transaction-per-call wrapper used by parallel/re-delivered workflows."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def finalize_if_ready(self, *, reference: AnalysisReference):
        async with self._session_factory() as session, session.begin():
            return await SqlAlchemyGarmentAnalysisFinalizationRepository(session).finalize_if_ready(
                reference=reference
            )
