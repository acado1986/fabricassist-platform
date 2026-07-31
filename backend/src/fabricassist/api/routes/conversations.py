"""Tenant-scoped scan conversations backed by PostgreSQL."""

from __future__ import annotations

# pyright: reportUnknownVariableType=false
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.ai_runs import create_conversation_run
from fabricassist.application.job_orchestration import publish_conversation_message
from fabricassist.application.jobs import (
    ConversationJobDispatcher,
    JobDispatchError,
    PermanentJobDispatchError,
)
from fabricassist.infrastructure.persistence.models import (
    ConversationMessage,
    ConversationThread,
    Scan,
    User,
)

router = APIRouter(prefix="/api/v1/scans", tags=["conversations"])


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: UUID
    role: str
    status: str
    text: str
    analysis_revision_id: UUID
    care_result_id: UUID
    uncertainties: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    run_id: UUID | None = None


class MessagePage(BaseModel):
    items: list[MessageResponse] = Field(default_factory=list)
    next_cursor: UUID | None = None


def string_items(value: object) -> list[str]:
    """Read both legacy JSON arrays and the current envelope without a 500 response."""
    raw = cast(dict[str, object], value).get("items", []) if isinstance(value, dict) else value
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_job_dispatcher() -> ConversationJobDispatcher:
    raise RuntimeError("Job dispatcher dependency was not configured.")


def response(message: ConversationMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role,
        status=message.status,
        text=message.text,
        analysis_revision_id=message.analysis_revision_id,
        care_result_id=message.care_result_id,
        uncertainties=string_items(message.uncertainties),
        follow_up_questions=string_items(message.follow_up_questions),
        run_id=message.run_id,
    )


async def scan_for(session: AsyncSession, user: User, scan_id: UUID) -> Scan:
    scan = await session.scalar(
        select(Scan).where(
            Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id
        )
    )
    if (
        scan is None
        or scan.garment_id is None
        or scan.active_analysis_revision_id is None
        or scan.active_result_id is None
    ):
        raise HTTPException(409, "An active garment analysis is required.")
    return scan


@router.get("/{scan_id}/messages", response_model=MessagePage)
async def list_messages(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    cursor: UUID | None = None,
    limit: int = 30,
) -> MessagePage:
    scan = await scan_for(session, user, scan_id)
    thread = await session.scalar(
        select(ConversationThread).where(
            ConversationThread.tenant_id == user.tenant_id,
            ConversationThread.garment_id == scan.garment_id,
        )
    )
    if thread is None:
        return MessagePage()
    statement = select(ConversationMessage).where(ConversationMessage.thread_id == thread.id)
    if cursor is not None:
        previous = await session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.id == cursor, ConversationMessage.thread_id == thread.id
            )
        )
        if previous is None:
            raise HTTPException(422, "Invalid message cursor.")
        statement = statement.where(
            or_(
                ConversationMessage.created_at > previous.created_at,
                (ConversationMessage.created_at == previous.created_at)
                & (ConversationMessage.id > previous.id),
            )
        )
    messages = list(
        (
            await session.scalars(
                statement.order_by(ConversationMessage.created_at, ConversationMessage.id).limit(
                    min(max(limit, 1), 100) + 1
                )
            )
        ).all()
    )
    more = len(messages) > min(max(limit, 1), 100)
    page = messages[: min(max(limit, 1), 100)]
    return MessagePage(
        items=[response(item) for item in page], next_cursor=page[-1].id if more else None
    )


@router.post("/{scan_id}/messages", response_model=MessageResponse, status_code=202)
async def post_message(
    scan_id: UUID,
    request: MessageRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[ConversationJobDispatcher, Depends(get_job_dispatcher)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MessageResponse:
    scan = await scan_for(session, user, scan_id)
    thread = await session.scalar(
        select(ConversationThread).where(
            ConversationThread.tenant_id == user.tenant_id,
            ConversationThread.garment_id == scan.garment_id,
        )
    )
    if thread is None:
        thread = ConversationThread(
            id=uuid4(),
            tenant_id=user.tenant_id,
            garment_id=scan.garment_id,
            user_id=user.id,
            active_analysis_revision_id=scan.active_analysis_revision_id,
        )
        session.add(thread)
        await session.flush()
    if idempotency_key:
        prior = await session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.thread_id == thread.id,
                ConversationMessage.idempotency_key == idempotency_key,
            )
        )
        if prior:
            if prior.dispatch_published_at is None:
                if prior.dispatch_correlation_id == str(UUID(int=0)):
                    prior.dispatch_correlation_id = str(http_request.state.correlation_id)
                    await session.commit()
                try:
                    await publish_conversation_message(
                        session=session,
                        message=prior,
                        dispatcher=dispatcher,
                    )
                except PermanentJobDispatchError as error:
                    raise HTTPException(502, "Conversation publication was rejected.") from error
                except JobDispatchError as error:
                    raise HTTPException(
                        503, "Conversation publication is temporarily unavailable."
                    ) from error
            return response(prior)
    message = ConversationMessage(
        id=uuid4(),
        tenant_id=user.tenant_id,
        thread_id=thread.id,
        scan_id=scan.id,
        garment_id=scan.garment_id,
        role="user",
        status="queued",
        text=request.text,
        idempotency_key=idempotency_key,
        analysis_revision_id=scan.active_analysis_revision_id,
        care_result_id=scan.active_result_id,
        dispatch_correlation_id=str(http_request.state.correlation_id),
    )
    session.add(message)
    await session.flush()
    run = await create_conversation_run(
        session,
        user=user,
        scan_id=scan.id,
        idempotency_key=idempotency_key or f"message:{message.id}",
        correlation_id=str(http_request.state.correlation_id),
        message_id=message.id,
    )
    message.run_id = run.id
    await session.commit()
    try:
        await publish_conversation_message(
            session=session,
            message=message,
            dispatcher=dispatcher,
        )
    except PermanentJobDispatchError as error:
        raise HTTPException(502, "Conversation publication was rejected.") from error
    except JobDispatchError as error:
        raise HTTPException(503, "Conversation publication is temporarily unavailable.") from error
    return response(message)
