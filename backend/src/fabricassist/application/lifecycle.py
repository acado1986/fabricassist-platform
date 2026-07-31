"""Review correction and privacy lifecycle use cases.

The database records intent before object storage is touched.  This makes deletion
retryable and prevents a transient storage failure from leaving a customer's
personal graph partially removed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.object_storage import (
    ObjectNotFoundError,
    ObjectStorage,
    PermanentObjectStorageError,
    RetryableObjectStorageError,
)
from fabricassist.application.planning import CarePlanningProvider
from fabricassist.domain.care import validate_care_plan
from fabricassist.domain.evidence import GarmentEvidenceDossier
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    AuditEvent,
    CareResult,
    ConversationThread,
    DeletionRequest,
    EvidenceCorrection,
    EvidenceDossier,
    Garment,
    GarmentIdentityConfirmation,
    GarmentServiceEvent,
    ModelRun,
    ObjectDeletionOutbox,
    ProposedPlan,
    RenderedAnswer,
    ReviewCase,
    RevisionImage,
    Scan,
    ScanImage,
    Tenant,
    ValidationReport,
)


def audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    event_type: str,
    resource_type: str,
    resource_id: UUID,
    safe_metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            safe_metadata=safe_metadata or {},
        )
    )


async def ensure_review_case(session: AsyncSession, scan: Scan) -> ReviewCase:
    if scan.active_analysis_revision_id is None:
        raise ValueError("An active analysis revision is required for review.")
    existing = await session.scalar(
        select(ReviewCase).where(
            ReviewCase.analysis_revision_id == scan.active_analysis_revision_id
        )
    )
    if isinstance(existing, ReviewCase):
        return existing
    review = ReviewCase(
        id=uuid4(),
        tenant_id=scan.tenant_id,
        scan_id=scan.id,
        garment_id=scan.garment_id,
        analysis_revision_id=scan.active_analysis_revision_id,
    )
    session.add(review)
    audit(
        session,
        tenant_id=scan.tenant_id,
        actor_user_id=None,
        event_type="review.opened",
        resource_type="review_case",
        resource_id=review.id,
    )
    return review


async def apply_human_correction(
    session: AsyncSession,
    *,
    review: ReviewCase,
    actor_id: UUID,
    dossier: GarmentEvidenceDossier,
    reason: str,
    care_planning_provider: CarePlanningProvider,
) -> CareResult:
    """Create successor artifacts; never mutate the provider's original evidence."""
    # Import here: analysis creates review cases, while corrections reuse its renderer.
    from fabricassist.application.analysis import TEMPLATE_VERSION, render_rich_result

    original = await session.get(AnalysisRevision, review.analysis_revision_id)
    if original is None:
        raise ValueError("Review source revision no longer exists.")
    scan = await session.get(Scan, review.scan_id)
    if scan is None:
        raise ValueError("Review scan no longer exists.")
    latest = await session.scalar(
        select(AnalysisRevision.revision_number)
        .where(AnalysisRevision.scan_id == scan.id)
        .order_by(AnalysisRevision.revision_number.desc())
        .limit(1)
    )
    revision = AnalysisRevision(
        id=uuid4(),
        tenant_id=review.tenant_id,
        scan_id=scan.id,
        garment_id=review.garment_id,
        revision_number=int(latest or 0) + 1,
        supersedes_revision_id=original.id,
        status="processing",
    )
    session.add(revision)
    prior_images = list(
        (
            await session.scalars(
                select(RevisionImage).where(RevisionImage.revision_id == original.id)
            )
        ).all()
    )
    for item in prior_images:
        session.add(
            RevisionImage(
                tenant_id=review.tenant_id, revision_id=revision.id, image_id=item.image_id
            )
        )
    evidence = EvidenceDossier(
        id=uuid4(),
        tenant_id=review.tenant_id,
        analysis_revision_id=revision.id,
        payload=dossier.model_dump(mode="json"),
    )
    session.add(evidence)
    planning_result = await care_planning_provider.propose_plan(dossier)
    proposal = planning_result.proposal
    session.add(
        ModelRun(
            id=uuid4(),
            tenant_id=review.tenant_id,
            scan_id=scan.id,
            operation="human_correction_planning",
            provider=planning_result.provider,
            model=planning_result.model,
            prompt_version="care-planning-v1",
            schema_version="proposed-care-plan-v1",
            request_fingerprint=hashlib.sha256(
                json.dumps(dossier.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest(),
            status="completed",
            latency_ms=planning_result.latency_ms,
            input_tokens=planning_result.input_tokens,
            output_tokens=planning_result.output_tokens,
            estimated_cost_usd=0 if planning_result.provider == "mock" else None,
        )
    )
    report = validate_care_plan(dossier, proposal)
    plan = ProposedPlan(
        id=uuid4(),
        tenant_id=review.tenant_id,
        analysis_revision_id=revision.id,
        retry_number=0,
        payload=proposal.model_dump(mode="json"),
    )
    session.add(plan)
    await session.flush()
    validation = ValidationReport(
        id=uuid4(),
        tenant_id=review.tenant_id,
        proposed_plan_id=plan.id,
        payload=report.model_dump(mode="json"),
    )
    session.add(validation)
    await session.flush()
    result = CareResult(
        id=uuid4(),
        tenant_id=review.tenant_id,
        analysis_revision_id=revision.id,
        dossier_id=evidence.id,
        proposed_plan_id=plan.id,
        validation_report_id=validation.id,
        status=report.outcome.value,
        canonical_data={
            "dossier": dossier.model_dump(mode="json"),
            "proposal": proposal.model_dump(mode="json"),
            "validation": report.model_dump(mode="json"),
        },
    )
    session.add(result)
    for language in ("en", "es"):
        session.add(
            RenderedAnswer(
                id=uuid4(),
                tenant_id=review.tenant_id,
                care_result_id=result.id,
                language=language,
                template_version=TEMPLATE_VERSION,
                answer=render_rich_result(dossier, proposal, report, language),
            )
        )
    revision.status = "completed"
    scan.active_analysis_revision_id = revision.id
    scan.active_result_id = result.id
    scan.status = (
        "completed"
        if report.outcome.value in {"passed", "passed_with_warnings"}
        else "needs_review"
    )
    if review.garment_id is not None:
        garment = await session.get(Garment, review.garment_id)
        if garment is not None:
            garment.active_analysis_revision_id = revision.id
            garment.active_result_id = result.id
    review.status = "corrected"
    review.approved_result_id = None
    session.add(
        EvidenceCorrection(
            id=uuid4(),
            tenant_id=review.tenant_id,
            review_case_id=review.id,
            original_revision_id=original.id,
            corrected_revision_id=revision.id,
            actor_user_id=actor_id,
            reason=reason,
            correction=dossier.model_dump(mode="json"),
        )
    )
    audit(
        session,
        tenant_id=review.tenant_id,
        actor_user_id=actor_id,
        event_type="review.corrected",
        resource_type="review_case",
        resource_id=review.id,
        safe_metadata={
            "new_revision_id": str(revision.id),
            "validation_outcome": report.outcome.value,
        },
    )
    return result


async def enqueue_deletion(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    resource_type: str,
    resource_id: UUID,
    images: list[ScanImage],
) -> DeletionRequest:
    request = await session.scalar(
        select(DeletionRequest).where(
            DeletionRequest.tenant_id == tenant_id,
            DeletionRequest.resource_type == resource_type,
            DeletionRequest.resource_id == resource_id,
        )
    )
    if isinstance(request, DeletionRequest):
        return request
    request = DeletionRequest(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    session.add(request)
    now = datetime.now(UTC)
    for image in images:
        image.deletion_requested_at = now
        session.add(
            ObjectDeletionOutbox(
                id=uuid4(),
                tenant_id=tenant_id,
                deletion_request_id=request.id,
                image_id=image.id,
                object_key=image.object_key,
            )
        )
    audit(
        session,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        event_type="deletion.requested",
        resource_type=resource_type,
        resource_id=resource_id,
        safe_metadata={"object_count": len(images)},
    )
    return request


async def retention_candidates(session: AsyncSession) -> list[ScanImage]:
    """Return private originals past tenant retention that have no queued deletion."""
    rows = await session.execute(
        select(ScanImage, Tenant)
        .join(Tenant, Tenant.id == ScanImage.tenant_id)
        .where(
            ScanImage.deleted_at.is_(None),
            ScanImage.deletion_requested_at.is_(None),
            ScanImage.completed_at.is_not(None),
        )
    )
    now = datetime.now(UTC)
    return [
        image
        for image, tenant in rows.all()
        if image.completed_at is not None
        and image.completed_at + timedelta(days=tenant.image_retention_days) <= now
    ]


async def cleanup_merged_garments(
    session: AsyncSession,
    *,
    grace_period_days: int = 30,
    limit: int = 100,
) -> int:
    """Permanently remove old merged garment tombstones after their grace period.

    Identity confirmation rows are removed explicitly because they retain a
    restrictive foreign key to the source garment. All analysis and image
    references should already point to the destination; the database cascade
    remains the final safety net for candidate and identifier rows.
    """
    cutoff = datetime.now(UTC) - timedelta(days=grace_period_days)
    garments = list(
        (
            await session.scalars(
                select(Garment)
                .where(
                    Garment.merged_into_id.is_not(None),
                    Garment.merged_at.is_not(None),
                    Garment.merged_at <= cutoff,
                    ~select(Scan.id).where(Scan.garment_id == Garment.id).exists(),
                    ~select(AnalysisRevision.id)
                    .where(AnalysisRevision.garment_id == Garment.id)
                    .exists(),
                    ~select(GarmentServiceEvent.id)
                    .where(GarmentServiceEvent.garment_id == Garment.id)
                    .exists(),
                    ~select(ConversationThread.id)
                    .where(ConversationThread.garment_id == Garment.id)
                    .exists(),
                )
                .order_by(Garment.merged_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    for garment in garments:
        audit(
            session,
            tenant_id=garment.tenant_id,
            actor_user_id=None,
            event_type="garment.merge_cleanup",
            resource_type="garment",
            resource_id=garment.id,
            safe_metadata={"target_garment_id": str(garment.merged_into_id)},
        )
        await session.execute(
            delete(GarmentIdentityConfirmation).where(
                GarmentIdentityConfirmation.garment_id == garment.id
            )
        )
        await session.delete(garment)
    if garments:
        await session.commit()
    return len(garments)


async def process_object_deletions(
    session: AsyncSession,
    storage: ObjectStorage,
    *,
    limit: int = 100,
    max_attempts: int = 5,
) -> int:
    """Claim and execute a bounded batch of durable object-deletion intents."""
    jobs = list(
        (
            await session.scalars(
                select(ObjectDeletionOutbox)
                .where(
                    or_(
                        ObjectDeletionOutbox.status == "pending",
                        and_(
                            ObjectDeletionOutbox.status == "failed",
                            ObjectDeletionOutbox.last_error_code == "OBJECT_DELETE_FAILED",
                            ObjectDeletionOutbox.attempts < max_attempts,
                        ),
                    )
                )
                .order_by(ObjectDeletionOutbox.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    completed = 0
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
        try:
            storage.delete_object(job.object_key)
        except ObjectNotFoundError:
            pass
        except RetryableObjectStorageError:
            job.status = "failed"
            job.last_error_code = "OBJECT_DELETE_FAILED"
            continue
        except PermanentObjectStorageError:
            job.status = "failed"
            job.last_error_code = "OBJECT_DELETE_REJECTED"
            continue
        job.status = "completed"
        job.deleted_at = datetime.now(UTC)
        job.last_error_code = None
        completed += 1
        if job.image_id is not None:
            image = await session.get(ScanImage, job.image_id)
            if image is not None:
                image.deleted_at = job.deleted_at
    requests = {job.deletion_request_id for job in jobs}
    for request_id in requests:
        request = await session.get(DeletionRequest, request_id)
        if request is not None:
            request_jobs = list(
                (
                    await session.scalars(
                        select(ObjectDeletionOutbox).where(
                            ObjectDeletionOutbox.deletion_request_id == request.id
                        )
                    )
                ).all()
            )
            if all(job.status == "completed" for job in request_jobs):
                request.status = "completed"
                request.completed_at = datetime.now(UTC)
            elif any(
                job.last_error_code == "OBJECT_DELETE_REJECTED"
                or (job.last_error_code == "OBJECT_DELETE_FAILED" and job.attempts >= max_attempts)
                for job in request_jobs
            ):
                request.status = "failed"
            else:
                request.status = "queued"
    await session.commit()
    return completed


async def run_retention_once(
    session: AsyncSession,
    storage: ObjectStorage,
    *,
    merged_garment_retention_days: int = 30,
    batch_size: int = 100,
    max_deletion_attempts: int = 5,
) -> tuple[int, int]:
    """Run one scheduler-independent retention pass.

    Cron, Celery, Render, or another scheduler can invoke this use case through
    its own thin adapter. PostgreSQL remains authoritative and all operations
    are bounded and retry-safe.
    """
    for image in await retention_candidates(session):
        await enqueue_deletion(
            session,
            tenant_id=image.tenant_id,
            user_id=None,
            resource_type="scan",
            resource_id=image.scan_id,
            images=[image],
        )
    await session.commit()
    merged = await cleanup_merged_garments(
        session,
        grace_period_days=merged_garment_retention_days,
        limit=batch_size,
    )
    deleted = await process_object_deletions(
        session,
        storage,
        limit=batch_size,
        max_attempts=max_deletion_attempts,
    )
    return merged, deleted
