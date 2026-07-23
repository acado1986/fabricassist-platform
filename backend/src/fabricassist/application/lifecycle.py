"""Review correction and privacy lifecycle use cases.

The database records intent before object storage is touched.  This makes deletion
retryable and prevents a transient storage failure from leaving a customer's
personal graph partially removed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.planning import MockCarePlanningProvider
from fabricassist.domain.care import validate_care_plan
from fabricassist.domain.evidence import GarmentEvidenceDossier
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    AuditEvent,
    CareResult,
    DeletionRequest,
    EvidenceCorrection,
    EvidenceDossier,
    Garment,
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
from fabricassist.infrastructure.storage.s3 import S3Storage


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
    proposal = await MockCarePlanningProvider().propose_plan(dossier)
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


async def process_object_deletions(
    session: AsyncSession, storage: S3Storage, *, limit: int = 100
) -> int:
    jobs = list(
        (
            await session.scalars(
                select(ObjectDeletionOutbox)
                .where(ObjectDeletionOutbox.status.in_(("pending", "failed")))
                .order_by(ObjectDeletionOutbox.created_at)
                .limit(limit)
            )
        ).all()
    )
    completed = 0
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
        try:
            storage.delete_object(job.object_key)
        except OSError:
            job.status = "failed"
            job.last_error_code = "OBJECT_DELETE_FAILED"
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
            outstanding = await session.scalar(
                select(ObjectDeletionOutbox.id)
                .where(
                    ObjectDeletionOutbox.deletion_request_id == request.id,
                    ObjectDeletionOutbox.status != "completed",
                )
                .limit(1)
            )
            if outstanding is None:
                request.status = "completed"
                request.completed_at = datetime.now(UTC)
    await session.commit()
    return completed
