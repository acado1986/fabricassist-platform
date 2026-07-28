"""Signed QStash delivery verification and durable checkpoint execution."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from enum import Enum

import jwt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.jobs import AnalysisJobMessage, JobDispatcher
from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan, ScanImage
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


def verify_qstash_signature(*, raw_body: bytes, signature: str | None, settings: Settings) -> None:
    """Verify a QStash JWT against raw bytes and the configured destination.

    QStash signs a SHA-256 body digest in ``body`` and the exact destination in
    ``sub``.  Trying current then next supports rotation without accepting an
    unsigned payload.  Claim failures are intentionally indistinguishable to
    callers.
    """
    if not signature:
        raise DeliveryVerificationError("missing signature")
    digest = hashlib.sha256(raw_body).hexdigest()
    for key in (settings.qstash_current_signing_key, settings.qstash_next_signing_key):
        if not key:
            continue
        try:
            claims = jwt.decode(signature, key, algorithms=["HS256"], options={"require": ["exp"]})
        except jwt.PyJWTError:
            continue
        if claims.get("sub") != settings.qstash_destination_url or claims.get("body") != digest:
            continue
        return
    raise DeliveryVerificationError("invalid signature")


def parse_delivery(raw_body: bytes) -> AnalysisJobMessage:
    try:
        return AnalysisJobMessage.model_validate_json(raw_body)
    except ValidationError as error:
        raise PermanentDeliveryError("permanently invalid job message") from error


async def execute_checkpoint(
    *, session: AsyncSession, message: AnalysisJobMessage, settings: Settings
) -> StageResult:
    """Claim and complete the existing first persisted stage exactly once.

    This phase deliberately checkpoints *validation* only.  The pre-existing
    Celery worker remains the sole owner of the legacy full-pipeline execution;
    that avoids a second analysis pipeline while providing the secure, durable
    HTTP execution seam required for later stage extraction.
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
        return StageResult.COMPLETE
    scan = await session.get(Scan, message.scan_id, with_for_update=True)
    if scan is None or scan.status == "deleted":
        operation.status = "obsolete"
        operation.completed_at = datetime.now(UTC)
        await session.commit()
        return StageResult.NOOP
    if operation.stage != message.stage:
        raise PermanentDeliveryError("message stage does not match operation")
    now = datetime.now(UTC)
    if operation.lease_expires_at is not None and operation.lease_expires_at > now:
        # A concurrent delivery has already claimed the row.  A 503 lets QStash
        # retry after the short DB lease, rather than double-processing.
        raise TemporaryJobError("job operation is leased")
    operation.lease_expires_at = now + timedelta(seconds=settings.job_stage_budget_seconds)
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
        return StageResult.NEEDS_BETTER_IMAGE
    scan.analysis_stage = message.stage
    scan.status = "queued"
    operation.status = "completed"
    operation.completed_at = now
    operation.lease_expires_at = None
    await session.commit()
    return StageResult.COMPLETE


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
            stage="validate_uploaded_images",
        )
        await dispatcher.dispatch_analysis(message, correlation_id=correlation_id)
        operation.published_at = datetime.now(UTC)
        published += 1
    await session.commit()
    return published
