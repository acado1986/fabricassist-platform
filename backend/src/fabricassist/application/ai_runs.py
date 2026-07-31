"""Shared durable AI-run lifecycle and replayable event helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.infrastructure.persistence.models import (
    AiRun,
    AiRunEvent,
    AiRunImage,
    ScanImage,
    User,
)

TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
ALLOWED_RUN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"pending", "running", "failed", "cancelled"}),
    "running": frozenset({"running", "completed", "failed", "cancelled"}),
    "completed": frozenset[str](),
    "failed": frozenset[str](),
    "cancelled": frozenset[str](),
}


class AiRunStateError(ValueError):
    """A requested durable run transition is invalid."""


def fingerprint(value: dict[str, Any]) -> str:
    """Create a stable, non-sensitive idempotency request fingerprint."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def append_run_event(
    session: AsyncSession,
    *,
    run: AiRun,
    event_type: str,
    data: dict[str, Any],
) -> AiRunEvent:
    """Append an ordered durable event in the caller's transaction."""
    next_sequence = (
        int(
            (
                await session.scalar(
                    select(func.coalesce(func.max(AiRunEvent.sequence), 0)).where(
                        AiRunEvent.run_id == run.id
                    )
                )
            )
            or 0
        )
        + 1
    )
    event = AiRunEvent(
        id=uuid4(),
        tenant_id=run.tenant_id,
        run_id=run.id,
        sequence=next_sequence,
        event_type=event_type,
        data=data,
    )
    session.add(event)
    await session.flush()
    return event


async def create_analysis_run(
    session: AsyncSession,
    *,
    user: User,
    scan_id: UUID,
    image_ids: list[UUID],
    idempotency_key: str,
    correlation_id: str,
) -> AiRun:
    """Create (or return) one authorized analysis run and its durable event."""
    request_fingerprint = fingerprint(
        {"scan_id": str(scan_id), "image_ids": sorted(map(str, image_ids))}
    )
    prior = await session.scalar(
        select(AiRun)
        .where(
            AiRun.tenant_id == user.tenant_id,
            AiRun.operation == "scan_analysis",
            AiRun.idempotency_key == idempotency_key,
        )
        .with_for_update()
    )
    if prior is not None:
        if prior.request_fingerprint != request_fingerprint:
            raise AiRunStateError("Idempotency key was already used for another request.")
        return prior
    images = list(
        (
            await session.scalars(
                select(ScanImage).where(
                    ScanImage.id.in_(image_ids),
                    ScanImage.scan_id == scan_id,
                    ScanImage.tenant_id == user.tenant_id,
                    ScanImage.completed_at.is_not(None),
                    ScanImage.deleted_at.is_(None),
                )
            )
        ).all()
    )
    if len(images) != len(set(image_ids)) or not images:
        raise AiRunStateError("Run image IDs must be completed images owned by this scan.")
    run = AiRun(
        id=uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        scan_id=scan_id,
        operation="scan_analysis",
        status="pending",
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        correlation_id=correlation_id,
    )
    session.add(run)
    await session.flush()
    session.add_all(
        [AiRunImage(tenant_id=user.tenant_id, run_id=run.id, image_id=image.id) for image in images]
    )
    await append_run_event(
        session, run=run, event_type="run.created", data={"image_count": len(images)}
    )
    return run


async def transition_run(
    session: AsyncSession,
    *,
    run: AiRun,
    status: str,
    event_type: str,
    data: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    """Apply a valid durable state transition and append its observable event."""
    if run.status in TERMINAL_RUN_STATUSES:
        return
    if status not in ALLOWED_RUN_TRANSITIONS.get(run.status, frozenset()):
        raise AiRunStateError(f"Cannot transition an AI run from {run.status} to {status}.")
    now = datetime.now(UTC)
    run.status = status
    if status == "running" and run.started_at is None:
        run.started_at = now
    if status in TERMINAL_RUN_STATUSES:
        run.completed_at = now
    run.error_code = error_code
    event_data = dict(data or {})
    if error_code is not None:
        event_data.setdefault("error_code", error_code)
    await append_run_event(session, run=run, event_type=event_type, data=event_data)


async def create_conversation_run(
    session: AsyncSession,
    *,
    user: User,
    scan_id: UUID,
    idempotency_key: str,
    correlation_id: str,
    message_id: UUID,
) -> AiRun:
    """Create a durable run for a queued conversation message."""
    request_fingerprint = fingerprint({"scan_id": str(scan_id), "message_id": str(message_id)})
    prior = await session.scalar(
        select(AiRun)
        .where(
            AiRun.tenant_id == user.tenant_id,
            AiRun.operation == "conversation_response",
            AiRun.idempotency_key == idempotency_key,
        )
        .with_for_update()
    )
    if prior is not None:
        if prior.request_fingerprint != request_fingerprint:
            raise AiRunStateError("Idempotency key was already used for another request.")
        return prior
    run = AiRun(
        id=uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        scan_id=scan_id,
        operation="conversation_response",
        status="pending",
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        correlation_id=correlation_id,
    )
    session.add(run)
    await session.flush()
    await append_run_event(
        session, run=run, event_type="run.created", data={"message_id": str(message_id)}
    )
    return run
