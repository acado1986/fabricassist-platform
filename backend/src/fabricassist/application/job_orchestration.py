"""Transport-neutral durable analysis dispatch orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.jobs import (
    AnalysisJobMessage,
    ConversationJobDispatcher,
    ConversationJobMessage,
    JobDispatcher,
    PermanentJobDispatchError,
)
from fabricassist.infrastructure.persistence.models import (
    AiRunImage,
    AnalysisJobOperation,
    AnalysisRevision,
    ConversationMessage,
    RevisionImage,
    Scan,
)

INITIAL_ANALYSIS_STAGE = "validate_uploaded_images"


def message_for(operation: AnalysisJobOperation) -> AnalysisJobMessage:
    """Build the canonical identifier-only message from committed outbox state."""
    return AnalysisJobMessage(
        scan_id=operation.scan_id,
        operation_key=operation.operation_key,
        revision_id=operation.revision_id,
        stage=INITIAL_ANALYSIS_STAGE
        if operation.stage == INITIAL_ANALYSIS_STAGE
        else "execute_analysis",
    )


async def publish_operation(
    *,
    session: AsyncSession,
    operation: AnalysisJobOperation,
    dispatcher: JobDispatcher,
) -> None:
    """Publish one committed intent and acknowledge it only after transport success."""
    try:
        await dispatcher.dispatch_analysis(
            message_for(operation),
            correlation_id=operation.correlation_id,
        )
    except PermanentJobDispatchError:
        operation.status = "failed"
        scan = await session.get(Scan, operation.scan_id)
        if scan is not None and scan.status not in {"completed", "deleted"}:
            scan.status = "failed"
            scan.analysis_stage = "failed"
            scan.analysis_error_code = "JOB_DISPATCH_PERMANENT"
        await session.commit()
        raise
    operation.published_at = datetime.now(UTC)
    await session.commit()


async def publish_conversation_message(
    *,
    session: AsyncSession,
    message: ConversationMessage,
    dispatcher: ConversationJobDispatcher,
) -> None:
    """Publish one committed conversation intent and persist acknowledgement."""
    try:
        await dispatcher.dispatch_conversation(
            ConversationJobMessage(conversation_message_id=message.id),
            correlation_id=message.dispatch_correlation_id,
        )
    except PermanentJobDispatchError:
        message.status = "failed"
        message.error_code = "JOB_DISPATCH_PERMANENT"
        await session.commit()
        raise
    message.dispatch_published_at = datetime.now(UTC)
    await session.commit()


async def enqueue_analysis(
    *,
    session: AsyncSession,
    scan: Scan,
    operation_key: str,
    correlation_id: str,
    dispatcher: JobDispatcher,
    run_id: UUID | None = None,
) -> AnalysisJobOperation:
    """Persist job intent before publishing through the selected adapter.

    Repeating a request republishes the same committed, unpublished operation.
    Transport deduplication plus database checkpoint claims make that recovery
    safe after a crash between commit and publication.
    """
    operation = await session.scalar(
        select(AnalysisJobOperation)
        .where(
            AnalysisJobOperation.scan_id == scan.id,
            AnalysisJobOperation.operation_key == operation_key,
            AnalysisJobOperation.stage == INITIAL_ANALYSIS_STAGE,
        )
        .with_for_update()
    )
    if operation is None:
        revision_id = uuid4()
        latest_revision = await session.scalar(
            select(func.max(AnalysisRevision.revision_number)).where(
                AnalysisRevision.scan_id == scan.id,
                AnalysisRevision.tenant_id == scan.tenant_id,
            )
        )
        revision = AnalysisRevision(
            id=revision_id,
            tenant_id=scan.tenant_id,
            scan_id=scan.id,
            garment_id=scan.garment_id,
            revision_number=int(latest_revision or 0) + 1,
            supersedes_revision_id=scan.active_analysis_revision_id,
            status="queued",
            module_version="garment-analysis-v2",
            workflow_version="asyncio-garment-analysis-v2",
            merged_schema_version="merged-garment-assessment-v2",
            care_policy_version="care-policy-v2",
            confidence_policy_version="confidence-policy-v1",
            retry_policy_version="branch-at-most-two-v1",
            effective_feature_flags={"stain_analysis": False},
        )
        session.add(revision)
        if run_id is not None:
            image_ids = list(
                (
                    await session.scalars(
                        select(AiRunImage.image_id).where(
                            AiRunImage.run_id == run_id,
                            AiRunImage.tenant_id == scan.tenant_id,
                        )
                    )
                ).all()
            )
        else:
            image_ids = []
        for image_id in image_ids:
            session.add(
                RevisionImage(
                    tenant_id=scan.tenant_id,
                    revision_id=revision_id,
                    image_id=image_id,
                )
            )
        operation = AnalysisJobOperation(
            id=uuid4(),
            scan_id=scan.id,
            revision_id=revision_id,
            operation_key=operation_key,
            stage=INITIAL_ANALYSIS_STAGE,
            correlation_id=correlation_id,
            run_id=run_id,
        )
        session.add(operation)
        scan.analysis_operation_key = operation_key
        scan.status = "queued"
        scan.analysis_stage = "queued"
        await session.commit()
    if operation.published_at is None:
        await publish_operation(session=session, operation=operation, dispatcher=dispatcher)
    return operation
