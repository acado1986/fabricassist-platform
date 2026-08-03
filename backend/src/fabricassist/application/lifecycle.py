"""Review correction and privacy lifecycle use cases.

The database records intent before object storage is touched.  This makes deletion
retryable and prevents a transient storage failure from leaving a customer's
personal graph partially removed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.object_storage import (
    ObjectNotFoundError,
    ObjectStorage,
    PermanentObjectStorageError,
    RetryableObjectStorageError,
)
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    AuditEvent,
    CareResult,
    DeletionRequest,
    EvidenceCorrection,
    ObjectDeletionOutbox,
    ReviewCase,
    RevisionImage,
    Scan,
    ScanImage,
    Tenant,
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


async def apply_human_correction_v2(
    session: AsyncSession,
    *,
    review: ReviewCase,
    actor_id: UUID,
    field_path: str,
    corrected_value: object,
    reason: str,
    source_image_id: UUID | None = None,
) -> CareResult:
    """Append a typed v2 overlay and deterministically finalize a successor.

    No care-planning model or legacy renderer participates in correction.
    """
    from fabricassist.application.garment_analysis import AnalysisReference
    from fabricassist.infrastructure.garment_analysis.persistence import (
        SqlAlchemyGarmentAnalysisFinalizationRepository,
    )
    from fabricassist.infrastructure.persistence.models import AnalysisBranchResult

    original = await session.get(AnalysisRevision, review.analysis_revision_id)
    scan = await session.get(Scan, review.scan_id, with_for_update=True)
    if original is None or scan is None:
        raise ValueError("Review source revision no longer exists.")
    if source_image_id is not None:
        permitted = await session.scalar(
            select(RevisionImage).where(
                RevisionImage.revision_id == original.id, RevisionImage.image_id == source_image_id
            )
        )
        if permitted is None:
            raise ValueError("Correction image is not part of the reviewed revision.")
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
        module_version=original.module_version,
        workflow_version=original.workflow_version,
        merged_schema_version=original.merged_schema_version,
        care_policy_version=original.care_policy_version,
        confidence_policy_version=original.confidence_policy_version,
        retry_policy_version=original.retry_policy_version,
        effective_feature_flags=dict(original.effective_feature_flags),
    )
    session.add(revision)
    for image in (
        await session.scalars(select(RevisionImage).where(RevisionImage.revision_id == original.id))
    ).all():
        session.add(
            RevisionImage(
                tenant_id=review.tenant_id, revision_id=revision.id, image_id=image.image_id
            )
        )
    for branch in (
        await session.scalars(
            select(AnalysisBranchResult).where(
                AnalysisBranchResult.analysis_revision_id == original.id
            )
        )
    ).all():
        if branch.status != "completed" or branch.result_payload is None:
            continue
        session.add(
            AnalysisBranchResult(
                id=uuid4(),
                tenant_id=review.tenant_id,
                analysis_revision_id=revision.id,
                branch_name=branch.branch_name,
                status="completed",
                attempt_count=branch.attempt_count,
                provider=branch.provider,
                model=branch.model,
                prompt_version=branch.prompt_version,
                schema_version=branch.schema_version,
                preprocessing_version=branch.preprocessing_version,
                request_fingerprint=branch.request_fingerprint,
                overall_confidence=branch.overall_confidence,
                uncertain_fields=list(branch.uncertain_fields),
                result_payload=dict(branch.result_payload),
                started_at=branch.started_at,
                completed_at=branch.completed_at,
            )
        )
    session.add(
        EvidenceCorrection(
            id=uuid4(),
            tenant_id=review.tenant_id,
            review_case_id=review.id,
            original_revision_id=original.id,
            corrected_revision_id=revision.id,
            actor_user_id=actor_id,
            reason=reason,
            correction={"field_path": field_path, "corrected_value": corrected_value},
            field_path=field_path,
            corrected_value=corrected_value,
            source_image_id=source_image_id,
            source="operator",
            confirmation="accepted",
        )
    )
    await session.flush()
    reference = AnalysisReference(
        tenant_id=review.tenant_id, scan_id=scan.id, run_id=uuid4(), revision_id=revision.id
    )
    finalized = await SqlAlchemyGarmentAnalysisFinalizationRepository(session).finalize_if_ready(
        reference=reference
    )
    if finalized is None:
        raise RuntimeError("Correction successor has incomplete v2 branch evidence.")
    result = await session.scalar(
        select(CareResult).where(CareResult.analysis_revision_id == revision.id)
    )
    if result is None:
        raise RuntimeError("V2 correction finalization did not persist a result.")
    review.status = "corrected"
    review.approved_result_id = None
    audit(
        session,
        tenant_id=review.tenant_id,
        actor_user_id=actor_id,
        event_type="review.corrected",
        resource_type="review_case",
        resource_id=review.id,
        safe_metadata={
            "new_revision_id": str(revision.id),
            "field_path": field_path,
            "validation_outcome": result.status,
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
