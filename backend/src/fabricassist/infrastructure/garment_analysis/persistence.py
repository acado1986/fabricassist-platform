"""SQLAlchemy persistence adapter for durable garment-analysis branch state."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, case, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.garment_analysis import (
    AnalysisBranch,
    BranchClaim,
    BranchCompletion,
    BranchState,
)
from fabricassist.infrastructure.persistence.models import (
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
            )
            for row in rows
        )

    async def complete_branch(
        self,
        *,
        tenant_id: UUID,
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
        await self._session.flush()
        return True
