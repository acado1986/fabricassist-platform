"""Signed QStash delivery verification and durable checkpoint execution."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import asyncio
import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import cast
from uuid import uuid4

import jwt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.analysis import analyse_scan
from fabricassist.application.jobs import (
    ANALYSIS_STAGES,
    AnalysisJobMessage,
    AnalysisStage,
    JobDispatcher,
)
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan, ScanImage
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import Settings


class DeliveryVerificationError(Exception):
    """A request which must not be allowed to enter the job executor."""


class PermanentDeliveryError(Exception):
    """A signed but malformed message which QStash must not retry."""


class TemporaryJobError(Exception):
    """A dependency failure which should be retried by QStash."""


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


def verify_qstash_signature(*, raw_body: bytes, signature: str | None, settings: Settings) -> None:
    """Verify a QStash JWT against raw bytes and the configured destination.

    QStash signs a SHA-256 body digest in ``body`` and the exact destination in
    ``sub``.  Trying current then next supports rotation without accepting an
    unsigned payload.  Claim failures are intentionally indistinguishable to
    callers.
    """
    if not signature:
        raise DeliveryVerificationError("missing signature")
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw_body).digest()).decode().rstrip("=")
    for key in (settings.qstash_current_signing_key, settings.qstash_next_signing_key):
        if not key:
            continue
        try:
            claims = jwt.decode(
                signature,
                key,
                algorithms=["HS256"],
                issuer="Upstash",
                options={"require": ["iss", "sub", "exp", "nbf", "body"]},
            )
        except jwt.PyJWTError:
            continue
        body_claim = str(claims.get("body", "")).rstrip("=")
        if claims.get("sub") != settings.qstash_destination_url or body_claim != digest:
            continue
        return
    raise DeliveryVerificationError("invalid signature")


def parse_delivery(raw_body: bytes) -> AnalysisJobMessage:
    try:
        return AnalysisJobMessage.model_validate_json(raw_body)
    except ValidationError as error:
        raise PermanentDeliveryError("permanently invalid job message") from error


async def execute_checkpoint(
    *,
    session: AsyncSession,
    message: AnalysisJobMessage,
    settings: Settings,
    database: Database | None = None,
    storage: S3Storage | None = None,
) -> CheckpointResult:
    """Claim one durable stage and return its unpublished continuation.

    Celery and QStash both invoke ``analyse_scan``.  QStash adds a short upload
    validation checkpoint before invoking that shared application use case, so
    transport selection never forks the care-analysis business rules.
    """
    operation = await session.scalar(
        select(AnalysisJobOperation)
        .where(
            AnalysisJobOperation.scan_id == message.scan_id,
            AnalysisJobOperation.operation_key == message.operation_key,
            AnalysisJobOperation.revision_id == message.revision_id,
        )
        .with_for_update()
    )
    if operation is None:
        raise PermanentDeliveryError("unknown job operation")
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
        raise PermanentDeliveryError("message stage does not match operation")
    now = datetime.now(UTC)
    if operation.lease_expires_at is not None and operation.lease_expires_at > now:
        # A concurrent delivery has already claimed the row.  A 503 lets QStash
        # retry after the short DB lease, rather than double-processing.
        raise TemporaryJobError("job operation is leased")
    operation.lease_expires_at = now + timedelta(seconds=settings.job_stage_budget_seconds)
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
            raise PermanentDeliveryError("analysis stage has no continuation")
        continuation = AnalysisJobOperation(
            id=uuid4(),
            scan_id=scan.id,
            revision_id=message.revision_id,
            operation_key=message.operation_key,
            stage=next_stage,
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

    if database is None or storage is None:
        raise TemporaryJobError("analysis runtime dependencies are unavailable")
    operation.status = "processing"
    scan.analysis_stage = message.stage
    scan.status = "processing"
    await session.commit()
    try:
        async with asyncio.timeout(max(1, settings.job_stage_budget_seconds - 5)):
            await analyse_scan(
                database=database,
                storage=storage,
                settings=settings,
                scan_id=message.scan_id,
            )
    except TimeoutError as error:
        raise TemporaryJobError("analysis stage exceeded its execution budget") from error
    operation.status = "completed"
    operation.completed_at = datetime.now(UTC)
    operation.lease_expires_at = None
    await session.commit()
    return CheckpointResult(StageResult.COMPLETE)


async def reconcile_unpublished_operations(
    *, session: AsyncSession, dispatcher: JobDispatcher, correlation_id: str
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
        await dispatcher.dispatch_analysis(message, correlation_id=correlation_id)
        operation.published_at = datetime.now(UTC)
        published += 1
    await session.commit()
    return published
