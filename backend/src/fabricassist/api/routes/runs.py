"""REST commands and SSE recovery stream for durable AI runs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from fabricassist.application.ai_runs import AiRunStateError, create_analysis_run, transition_run
from fabricassist.application.job_orchestration import enqueue_analysis
from fabricassist.application.jobs import JobDispatcher
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import AiRun, AiRunEvent, AiRunImage, Scan, User
from fabricassist.infrastructure.telemetry import SSE_CONNECTIONS, SSE_DISCONNECTS

router = APIRouter(prefix="/api/v1", tags=["runs"])


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_ids: list[UUID] = Field(min_length=1, max_length=8)


class RunResponse(BaseModel):
    run_id: UUID
    scan_id: UUID
    status: str
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_job_dispatcher() -> JobDispatcher:
    raise RuntimeError("Job dispatcher dependency was not configured.")


async def get_database() -> Database:
    raise RuntimeError("Database dependency was not configured.")


async def owned_run(
    session: AsyncSession, user: User, run_id: UUID, *, for_update: bool = False
) -> AiRun:
    statement = select(AiRun).where(
        AiRun.id == run_id, AiRun.tenant_id == user.tenant_id, AiRun.user_id == user.id
    )
    if for_update:
        statement = statement.with_for_update()
    run = await session.scalar(statement)
    if run is None:
        raise HTTPException(404, "Run was not found.")
    return run


def response(run: AiRun) -> RunResponse:
    return RunResponse(
        run_id=run.id,
        scan_id=run.scan_id,
        status=run.status,
        error_code=run.error_code,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/scans/{scan_id}/runs", response_model=RunResponse, status_code=202)
async def start_run(
    scan_id: UUID,
    body: StartRunRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunResponse:
    scan = await session.scalar(
        select(Scan)
        .where(Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id)
        .with_for_update()
    )
    if scan is None:
        raise HTTPException(404, "Scan was not found.")
    if scan.status not in {"draft", "uploading", "queued", "failed", "needs_better_image"}:
        raise HTTPException(409, "A new analysis run cannot start in this scan state.")
    key = idempotency_key or f"run:{scan_id}:{','.join(sorted(map(str, body.image_ids)))}"
    try:
        run = await create_analysis_run(
            session,
            user=user,
            scan_id=scan.id,
            image_ids=body.image_ids,
            idempotency_key=key,
            correlation_id=str(request.state.correlation_id),
        )
    except AiRunStateError as error:
        raise HTTPException(409, str(error)) from error
    if run.status == "pending":
        operation = await enqueue_analysis(
            session=session,
            scan=scan,
            operation_key=f"run:{run.id}",
            correlation_id=run.correlation_id,
            dispatcher=dispatcher,
            run_id=run.id,
        )
        if operation.status == "failed":
            await transition_run(
                session,
                run=run,
                status="failed",
                event_type="run.failed",
                error_code="JOB_DISPATCH_PERMANENT",
            )
            await session.commit()
    return response(run)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RunResponse:
    return response(await owned_run(session, user, run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RunResponse:
    run = await owned_run(session, user, run_id, for_update=True)
    if run.status not in {"pending", "running"}:
        return response(run)
    # Gemini calls are not safely interruptible through the provider port. The
    # durable intent makes workers discard a late terminal result instead of
    # publishing it after cancellation wins.
    run.cancel_requested_at = datetime.now(UTC)
    await transition_run(session, run=run, status="cancelled", event_type="run.cancelled")
    await session.commit()
    return response(run)


@router.post("/runs/{run_id}/retry", response_model=RunResponse, status_code=202)
async def retry_run(
    run_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunResponse:
    prior = await owned_run(session, user, run_id, for_update=True)
    if prior.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled runs can be retried.")
    image_ids = list(
        (
            await session.scalars(select(AiRunImage.image_id).where(AiRunImage.run_id == prior.id))
        ).all()
    )
    key = idempotency_key or f"retry:{prior.id}"
    try:
        run = await create_analysis_run(
            session,
            user=user,
            scan_id=prior.scan_id,
            image_ids=image_ids,
            idempotency_key=key,
            correlation_id=str(request.state.correlation_id),
        )
    except AiRunStateError as error:
        raise HTTPException(409, str(error)) from error
    run.parent_run_id = prior.id
    scan = await session.get(Scan, prior.scan_id, with_for_update=True)
    if scan is None:
        raise HTTPException(409, "The scan is no longer available.")
    await enqueue_analysis(
        session=session,
        scan=scan,
        operation_key=f"run:{run.id}",
        correlation_id=run.correlation_id,
        dispatcher=dispatcher,
        run_id=run.id,
    )
    return response(run)


def sse_frame(event: AiRunEvent) -> bytes:
    payload = {
        "schema_version": 1,
        "event_id": str(event.id),
        "run_id": str(event.run_id),
        "sequence": event.sequence,
        "timestamp": event.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "data": event.data,
    }
    import json

    encoded = json.dumps(payload, separators=(",", ":"))
    return f"id: {event.sequence}\nevent: {event.event_type}\ndata: {encoded}\n\n".encode()


@router.get("/runs/{run_id}/events", response_class=StreamingResponse)
async def run_events(
    run_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    database: Annotated[Database, Depends(get_database)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    await owned_run(session, user, run_id)
    try:
        cursor = max(0, int(last_event_id or "0"))
    except ValueError as error:
        raise HTTPException(422, "Last-Event-ID must be an event sequence.") from error

    # Release the request-scoped transaction before a potentially long stream.
    # Each poll below uses a short independent PostgreSQL transaction instead.
    await session.rollback()

    async def stream() -> AsyncIterator[bytes]:
        nonlocal cursor
        heartbeat_after = 0
        terminal = False
        SSE_CONNECTIONS.inc()
        try:
            while True:
                if await request.is_disconnected():
                    return
                events = await _events_after(database, run_id=run_id, cursor=cursor)
                for event in events:
                    cursor = event.sequence
                    yield sse_frame(event)
                    if event.event_type in {"run.completed", "run.failed", "run.cancelled"}:
                        terminal = True
                        return
                heartbeat_after += 1
                if heartbeat_after >= 15:
                    heartbeat_after = 0
                    yield b"event: heartbeat\ndata: {}\n\n"
                await asyncio.sleep(1)
        finally:
            SSE_CONNECTIONS.dec()
            if not terminal:
                SSE_DISCONNECTS.inc()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


async def _events_after(database: Database, *, run_id: UUID, cursor: int) -> list[AiRunEvent]:
    """Read a replay page without pinning a database transaction to the SSE connection."""
    async with database.session_factory() as event_session:
        return list(
            (
                await event_session.scalars(
                    select(AiRunEvent)
                    .where(AiRunEvent.run_id == run_id, AiRunEvent.sequence > cursor)
                    .order_by(AiRunEvent.sequence)
                )
            ).all()
        )
