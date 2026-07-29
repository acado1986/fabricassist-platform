"""Transport-neutral durable analysis checkpoint execution."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.analysis import analyse_scan
from fabricassist.application.cache import HotCache
from fabricassist.application.jobs import (
    ANALYSIS_STAGES,
    AnalysisJobMessage,
    AnalysisStage,
    ConversationJobMessage,
    JobDispatcher,
    PermanentJobDispatchError,
    RetryableJobDispatchError,
)
from fabricassist.application.limits import (
    ConcurrencyGate,
    ConcurrencyLimitExceeded,
    LimitBackendUnavailable,
)
from fabricassist.application.object_storage import (
    ObjectNotFoundError,
    ObjectStorage,
    PermanentObjectStorageError,
    RetryableObjectStorageError,
)
from fabricassist.application.planning import CarePlanningProvider
from fabricassist.application.policies import AnalysisExecutionPolicy, JobExecutionPolicy
from fabricassist.application.product_information import ProductInformationProvider
from fabricassist.application.vision import VisionEvidenceProvider, VisionProviderError
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    ConversationMessage,
    Scan,
    ScanImage,
)

logger = logging.getLogger(__name__)


class PermanentJobMessageError(Exception):
    """An invalid or unknown message that a transport must not retry."""


class TemporaryJobError(Exception):
    """A dependency failure which the selected transport should retry."""


class AnalysisExecutionError(PermanentJobMessageError):
    """A durably recorded analysis failure safe to expose only as a code."""

    def __init__(self, code: str, cause: Exception) -> None:
        super().__init__(code)
        self.code = code
        self.cause_type = type(cause).__name__


class StageResult(str, Enum):
    COMPLETE = "complete"
    NOOP = "noop"
    BLOCKED = "blocked"
    NEEDS_BETTER_IMAGE = "needs_better_image"


@dataclass(frozen=True)
class CheckpointResult:
    outcome: StageResult
    continuation: AnalysisJobMessage | None = None


def _next_stage(stage: AnalysisStage) -> AnalysisStage | None:
    index = ANALYSIS_STAGES.index(stage)
    return ANALYSIS_STAGES[index + 1] if index + 1 < len(ANALYSIS_STAGES) else None


def _message(operation: AnalysisJobOperation) -> AnalysisJobMessage:
    return AnalysisJobMessage(
        scan_id=operation.scan_id,
        operation_key=operation.operation_key,
        revision_id=operation.revision_id,
        stage=cast(AnalysisStage, operation.stage),
    )


async def execute_checkpoint(
    *,
    session: AsyncSession,
    message: AnalysisJobMessage,
    execution_policy: JobExecutionPolicy,
    analysis_policy: AnalysisExecutionPolicy | None = None,
    database: Database | None = None,
    storage: ObjectStorage | None = None,
    evidence_provider: VisionEvidenceProvider | None = None,
    care_planning_provider: CarePlanningProvider | None = None,
    product_information_provider: ProductInformationProvider | None = None,
    hot_cache: HotCache | None = None,
    concurrency_gate: ConcurrencyGate | None = None,
) -> CheckpointResult:
    """Claim one durable stage and return its unpublished continuation.

    Celery and QStash both traverse the same upload-validation checkpoint before
    invoking the shared analysis use case, so transport selection never forks
    care-analysis business rules.
    """
    operation = await session.scalar(
        select(AnalysisJobOperation)
        .where(
            AnalysisJobOperation.scan_id == message.scan_id,
            AnalysisJobOperation.operation_key == message.operation_key,
            AnalysisJobOperation.revision_id == message.revision_id,
            AnalysisJobOperation.stage == message.stage,
        )
        .with_for_update()
    )
    if operation is None:
        raise PermanentJobMessageError("unknown job operation")
    if operation.status == "completed":
        next_stage = _next_stage(message.stage)
        if next_stage is None:
            return CheckpointResult(StageResult.COMPLETE)
        continuation = await session.scalar(
            select(AnalysisJobOperation).where(
                AnalysisJobOperation.scan_id == message.scan_id,
                AnalysisJobOperation.operation_key == message.operation_key,
                AnalysisJobOperation.revision_id == message.revision_id,
                AnalysisJobOperation.stage == next_stage,
                AnalysisJobOperation.published_at.is_(None),
            )
        )
        return CheckpointResult(
            StageResult.COMPLETE,
            _message(continuation) if isinstance(continuation, AnalysisJobOperation) else None,
        )
    scan = await session.get(Scan, message.scan_id, with_for_update=True)
    if scan is None or scan.status == "deleted":
        operation.status = "obsolete"
        operation.completed_at = datetime.now(UTC)
        await session.commit()
        return CheckpointResult(StageResult.NOOP)
    if operation.stage != message.stage:
        raise PermanentJobMessageError("message stage does not match operation")
    now = datetime.now(UTC)
    if operation.lease_expires_at is not None and operation.lease_expires_at > now:
        # A concurrent delivery has already claimed the row.  A 503 lets QStash
        # retry after the short DB lease, rather than double-processing.
        raise TemporaryJobError("job operation is leased")
    operation.lease_expires_at = now + timedelta(seconds=execution_policy.stage_budget_seconds)
    if message.stage == "validate_uploaded_images":
        image_count = await session.scalar(
            select(ScanImage.id)
            .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
            .limit(1)
        )
        if image_count is None:
            scan.status = "needs_better_image"
            scan.analysis_error_code = "UPLOAD_MISSING"
            scan.progress_percent = 100
            operation.status = "completed"
            operation.completed_at = now
            operation.lease_expires_at = None
            await session.commit()
            return CheckpointResult(StageResult.NEEDS_BETTER_IMAGE)
        next_stage = _next_stage(message.stage)
        if next_stage is None:  # pragma: no cover - guarded by the stage contract
            raise PermanentJobMessageError("analysis stage has no continuation")
        continuation = AnalysisJobOperation(
            id=uuid4(),
            scan_id=scan.id,
            revision_id=message.revision_id,
            operation_key=message.operation_key,
            stage=next_stage,
            correlation_id=operation.correlation_id,
        )
        session.add(continuation)
        scan.analysis_stage = next_stage
        scan.status = "queued"
        scan.progress_percent = 10
        operation.status = "completed"
        operation.completed_at = now
        operation.lease_expires_at = None
        await session.commit()
        return CheckpointResult(StageResult.COMPLETE, _message(continuation))

    if (
        database is None
        or storage is None
        or evidence_provider is None
        or care_planning_provider is None
        or product_information_provider is None
        or hot_cache is None
        or concurrency_gate is None
        or analysis_policy is None
    ):
        raise TemporaryJobError("analysis runtime dependencies are unavailable")
    operation.status = "processing"
    scan.analysis_stage = message.stage
    scan.status = "processing"
    await session.commit()
    try:
        async with asyncio.timeout(max(1, execution_policy.stage_budget_seconds - 5)):
            async with concurrency_gate.slot(
                tenant_id=str(scan.tenant_id),
                operation="analysis",
            ):
                await analyse_scan(
                    database=database,
                    storage=storage,
                    scan_id=message.scan_id,
                    evidence_provider=evidence_provider,
                    care_planning_provider=care_planning_provider,
                    product_information_provider=product_information_provider,
                    hot_cache=hot_cache,
                    policy=analysis_policy,
                )
    except (TimeoutError, RetryableObjectStorageError) as error:
        # A retry must be able to claim this row immediately. Leaving it in
        # ``processing`` until its old lease expires turns a bounded transport
        # retry into a customer-visible spinner.
        operation.status = "queued"
        operation.lease_expires_at = None
        scan.status = "queued"
        scan.analysis_stage = message.stage
        await session.commit()
        logger.warning(
            "Analysis execution will be retried",
            extra={"error_type": type(error).__name__},
        )
        raise TemporaryJobError("analysis stage exceeded its execution budget") from error
    except (ConcurrencyLimitExceeded, LimitBackendUnavailable) as error:
        operation.status = "queued"
        operation.lease_expires_at = None
        scan.status = "queued"
        scan.analysis_stage = message.stage
        await session.commit()
        raise TemporaryJobError("analysis concurrency is temporarily unavailable") from error
    except (ObjectNotFoundError, PermanentObjectStorageError, VisionProviderError) as error:
        error_code = (
            error.code if isinstance(error, VisionProviderError) else "ANALYSIS_STORAGE_ERROR"
        )
        operation.status = "failed"
        operation.completed_at = datetime.now(UTC)
        operation.lease_expires_at = None
        scan.status = "failed"
        scan.analysis_stage = "failed"
        scan.analysis_error_code = error_code
        scan.progress_percent = 100
        await session.commit()
        logger.error(
            "Analysis execution failed permanently",
            extra={"error_type": type(error).__name__},
        )
        raise AnalysisExecutionError(error_code, error) from error
    except Exception as error:
        # Persist a safe terminal code before returning a non-retryable delivery
        # response. The underlying exception type is retained only in structured
        # server logs with the request correlation context.
        operation.status = "failed"
        operation.completed_at = datetime.now(UTC)
        operation.lease_expires_at = None
        scan.status = "failed"
        scan.analysis_stage = "failed"
        scan.analysis_error_code = "ANALYSIS_INTERNAL_ERROR"
        scan.progress_percent = 100
        await session.commit()
        logger.exception(
            "Analysis execution failed unexpectedly",
            extra={"error_type": type(error).__name__},
        )
        raise AnalysisExecutionError("ANALYSIS_INTERNAL_ERROR", error) from error
    operation.status = "completed"
    operation.completed_at = datetime.now(UTC)
    operation.lease_expires_at = None
    await session.commit()
    return CheckpointResult(StageResult.COMPLETE)


async def reconcile_unpublished_operations(
    *,
    session: AsyncSession,
    dispatcher: JobDispatcher,
    correlation_id: str,
    limit: int = 100,
) -> int:
    """Publish durable, unacknowledged operations after a post-commit failure.

    Calling this from a scheduled worker or an operational recovery command is
    safe: QStash's deterministic id is stable and the executor is idempotent.
    """
    operations = list(
        (
            await session.scalars(
                select(AnalysisJobOperation)
                .where(
                    AnalysisJobOperation.status == "queued",
                    AnalysisJobOperation.published_at.is_(None),
                )
                .order_by(AnalysisJobOperation.created_at, AnalysisJobOperation.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    published = 0
    for operation in operations:
        message = AnalysisJobMessage(
            scan_id=operation.scan_id,
            operation_key=operation.operation_key,
            revision_id=operation.revision_id,
            stage=cast(AnalysisStage, operation.stage),
        )
        try:
            await dispatcher.dispatch_analysis(
                message,
                correlation_id=operation.correlation_id or correlation_id,
            )
        except RetryableJobDispatchError:
            continue
        except PermanentJobDispatchError:
            operation.status = "failed"
            scan = await session.get(Scan, operation.scan_id)
            if scan is not None and scan.status not in {"completed", "deleted"}:
                scan.status = "failed"
                scan.analysis_stage = "failed"
                scan.analysis_error_code = "JOB_DISPATCH_PERMANENT"
            continue
        operation.published_at = datetime.now(UTC)
        published += 1
    await session.commit()
    return published


async def reconcile_unpublished_conversations(
    *,
    session: AsyncSession,
    dispatcher: JobDispatcher,
    limit: int = 100,
) -> int:
    """Republish committed conversation intents without duplicating messages."""
    messages = list(
        (
            await session.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.role == "user",
                    ConversationMessage.status == "queued",
                    ConversationMessage.dispatch_published_at.is_(None),
                )
                .order_by(ConversationMessage.created_at, ConversationMessage.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    published = 0
    for message in messages:
        try:
            await dispatcher.dispatch_conversation(
                ConversationJobMessage(conversation_message_id=message.id),
                correlation_id=message.dispatch_correlation_id,
            )
        except RetryableJobDispatchError:
            continue
        except PermanentJobDispatchError:
            message.status = "failed"
            message.error_code = "JOB_DISPATCH_PERMANENT"
            continue
        message.dispatch_published_at = datetime.now(UTC)
        published += 1
    await session.commit()
    return published
