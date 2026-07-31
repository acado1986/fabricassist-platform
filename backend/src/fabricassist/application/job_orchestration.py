"""Transport-neutral durable analysis dispatch orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.jobs import (
    AnalysisJobMessage,
    ConversationJobDispatcher,
    ConversationJobMessage,
    JobDispatcher,
    PermanentJobDispatchError,
)
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    ConversationMessage,
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
        operation = AnalysisJobOperation(
            id=uuid4(),
            scan_id=scan.id,
            revision_id=uuid4(),
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
