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
from fabricassist.domain.garment_analysis.parity import ExecutionSnapshot
from fabricassist.infrastructure.persistence.models import (
    AiRunImage,
    AnalysisJobOperation,
    AnalysisRevision,
    ConversationMessage,
    Garment,
    GarmentIdentifier,
    RevisionImage,
    Scan,
)
from fabricassist.settings import ModelCapabilityProvider, Settings

INITIAL_ANALYSIS_STAGE = "validate_uploaded_images"


def execution_snapshot_for(settings: Settings) -> ExecutionSnapshot:
    """Freeze the configured v2 behavior before a revision is queued."""
    provider = settings.garment_analysis_provider.value
    if settings.garment_analysis_provider is ModelCapabilityProvider.GEMINI:
        model = settings.garment_analysis_gemini_model or settings.gemini_model
    elif settings.garment_analysis_provider is ModelCapabilityProvider.OPENAI_RESPONSES:
        model = settings.garment_analysis_openai_model or settings.openai_responses_model
    else:
        model = "deterministic-garment-analysis"
    return ExecutionSnapshot(
        module_version="garment-analysis-v2",
        workflow_version="asyncio-garment-analysis-v2",
        provider=provider,
        model=model,
        prompt_versions={
            "garment_inspection": "garment_inspection-v1",
            "label_extraction": "label_extraction-v1",
            "barcode_enrichment": "barcode_enrichment-v1",
        },
        schema_versions={
            "merged_assessment": "merged-garment-assessment-v2",
            "barcode_enrichment": "barcode-enrichment-v2",
        },
        preprocessing_version="normalized-jpeg-v2",
        branch_routing_version="branch-routing-v2",
        cache_version="parity-cache-v2",
        product_adapter_version=f"product-lookup-{settings.product_information_provider.value}-v2",
        identity_policy_version="identity-policy-v2",
        care_policy_version="care-policy-v2",
        rendering_version="care-rendering-v2",
        effective_feature_flags={
            "stain_analysis": settings.garment_analysis_stain_enabled,
            "barcode_enrichment": True,
        },
    )


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
    settings: Settings,
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
        # The v2 workflow creates its revision before worker execution.  A new
        # scan therefore needs its physical garment bootstrapped here rather
        # than relying on the removed legacy analysis path to create it later.
        if scan.garment_id is None:
            garment_id = uuid4()
            session.add(
                Garment(
                    id=garment_id,
                    tenant_id=scan.tenant_id,
                    user_id=scan.user_id,
                )
            )
            session.add(
                GarmentIdentifier(
                    id=uuid4(),
                    tenant_id=scan.tenant_id,
                    garment_id=garment_id,
                    identifier_type="fabricassist_serial",
                    normalized_value=f"FA-{garment_id.hex.upper()}",
                )
            )
            scan.garment_id = garment_id
        revision_id = uuid4()
        predecessor_revision_id = scan.active_analysis_revision_id
        if predecessor_revision_id is None:
            predecessor_revision_id = await session.scalar(
                select(AnalysisRevision.id)
                .where(
                    AnalysisRevision.tenant_id == scan.tenant_id,
                    AnalysisRevision.garment_id == scan.garment_id,
                )
                .order_by(
                    AnalysisRevision.revision_number.desc(),
                    AnalysisRevision.created_at.desc(),
                )
                .limit(1)
            )
        execution_snapshot = execution_snapshot_for(settings)
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
            supersedes_revision_id=predecessor_revision_id,
            status="queued",
            module_version="garment-analysis-v2",
            workflow_version="asyncio-garment-analysis-v2",
            merged_schema_version="merged-garment-assessment-v2",
            care_policy_version="care-policy-v2",
            confidence_policy_version="confidence-policy-v1",
            retry_policy_version="branch-at-most-two-v1",
            effective_feature_flags={"stain_analysis": False, "barcode_enrichment": True},
            execution_snapshot=execution_snapshot.model_dump(mode="json"),
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
