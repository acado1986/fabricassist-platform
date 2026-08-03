"""Private, signed job-delivery endpoint (excluded from the public schema)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from fabricassist.application.conversation_provider import ConversationProvider
from fabricassist.application.conversations import answer_message_by_id
from fabricassist.application.garment_analysis import GarmentAnalysisWorkflow
from fabricassist.application.job_execution import (
    AnalysisExecutionError,
    PermanentJobMessageError,
    TemporaryJobError,
    execute_checkpoint,
)
from fabricassist.application.job_orchestration import publish_operation
from fabricassist.application.jobs import (
    ConversationJobMessage,
    JobDispatcher,
    JobDispatchError,
    PermanentJobDispatchError,
)
from fabricassist.application.limits import ConcurrencyGate
from fabricassist.application.policies import ConversationPolicy, JobExecutionPolicy
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.jobs.qstash_inbound import (
    DeliveryVerificationError,
    QStashDeliveryVerifier,
)
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    ConversationMessage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/jobs", include_in_schema=False)


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_database() -> Database:
    raise RuntimeError("Database dependency was not configured.")


async def get_job_dispatcher() -> JobDispatcher:
    raise RuntimeError("Job dispatcher dependency was not configured.")


async def get_qstash_verifier() -> QStashDeliveryVerifier:
    raise RuntimeError("QStash verifier dependency was not configured.")


async def get_concurrency_gate() -> ConcurrencyGate:
    raise RuntimeError("Concurrency-gate dependency was not configured.")


async def get_garment_analysis_workflow() -> GarmentAnalysisWorkflow:
    raise RuntimeError("Garment-analysis workflow dependency was not configured.")


async def get_conversation_provider() -> ConversationProvider:
    raise RuntimeError("Conversation-provider dependency was not configured.")


async def get_job_execution_policy() -> JobExecutionPolicy:
    raise RuntimeError("Job execution policy dependency was not configured.")


async def get_conversation_policy() -> ConversationPolicy:
    raise RuntimeError("Conversation policy dependency was not configured.")


@router.post("/qstash", status_code=204)
async def execute_stage(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    database: Annotated[Database, Depends(get_database)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    verifier: Annotated[QStashDeliveryVerifier, Depends(get_qstash_verifier)],
    concurrency_gate: Annotated[ConcurrencyGate, Depends(get_concurrency_gate)],
    garment_analysis_workflow: Annotated[
        GarmentAnalysisWorkflow, Depends(get_garment_analysis_workflow)
    ],
    conversation_provider: Annotated[
        ConversationProvider,
        Depends(get_conversation_provider),
    ],
    job_execution_policy: Annotated[
        JobExecutionPolicy,
        Depends(get_job_execution_policy),
    ],
    conversation_policy: Annotated[ConversationPolicy, Depends(get_conversation_policy)],
    signature: Annotated[str | None, Header(alias="Upstash-Signature")] = None,
) -> Response:
    raw_body = await request.body()
    try:
        verifier.verify(raw_body=raw_body, signature=signature)
        message = verifier.parse(raw_body)
        if isinstance(message, ConversationJobMessage):
            conversation = await session.get(ConversationMessage, message.conversation_message_id)
            tenant_id = str(conversation.tenant_id) if conversation is not None else "missing"
            async with concurrency_gate.slot(
                tenant_id=tenant_id,
                operation="conversation",
            ):
                await answer_message_by_id(
                    database,
                    message.conversation_message_id,
                    conversation_provider,
                    conversation_policy,
                )
            return Response(status_code=204)
        result = await execute_checkpoint(
            session=session,
            message=message,
            execution_policy=job_execution_policy,
            garment_analysis_workflow=garment_analysis_workflow,
            concurrency_gate=concurrency_gate,
        )
        if result.continuation is not None:
            continuation = await session.scalar(
                select(AnalysisJobOperation).where(
                    AnalysisJobOperation.scan_id == result.continuation.scan_id,
                    AnalysisJobOperation.operation_key == result.continuation.operation_key,
                    AnalysisJobOperation.revision_id == result.continuation.revision_id,
                    AnalysisJobOperation.stage == result.continuation.stage,
                )
            )
            if isinstance(continuation, AnalysisJobOperation):
                await publish_operation(
                    session=session,
                    operation=continuation,
                    dispatcher=dispatcher,
                )
    except DeliveryVerificationError:
        return Response(status_code=401)
    except AnalysisExecutionError as error:
        # The execution layer already persisted a redacted terminal status. Do
        # not let QStash retry an internal error indefinitely or retain payloads.
        logger.error(
            "QStash analysis delivery reached a terminal execution failure",
            extra={"error_type": error.cause_type},
        )
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except PermanentJobMessageError:
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except TemporaryJobError:
        return Response(status_code=503)
    except PermanentJobDispatchError:
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except JobDispatchError:
        return Response(status_code=503)
    return Response(status_code=204)
