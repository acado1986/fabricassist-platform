"""Tenant-scoped scan conversations backed by PostgreSQL."""

from __future__ import annotations

# pyright: reportUnknownVariableType=false
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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


class MessagePage(BaseModel):
    items: list[MessageResponse] = Field(default_factory=list)
    next_cursor: UUID | None = None


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


def response(message: ConversationMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role,
        status=message.status,
        text=message.text,
        analysis_revision_id=message.analysis_revision_id,
        care_result_id=message.care_result_id,
        uncertainties=message.uncertainties.get("items", []),
        follow_up_questions=message.follow_up_questions.get("items", []),
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
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
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
    )
    session.add(message)
    await session.commit()
    from fabricassist.worker.tasks import answer_message_task

    answer_message_task.delay(str(message.id))  # pyright: ignore[reportCallIssue]
    return response(message)
