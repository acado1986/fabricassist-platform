"""Private, signed job-delivery endpoint (excluded from the public schema)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from fabricassist.application.cache import HotCache
from fabricassist.application.conversation_provider import ConversationProvider
from fabricassist.application.conversations import answer_message_by_id
from fabricassist.application.job_execution import (
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
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.application.planning import CarePlanningProvider
from fabricassist.application.policies import (
    AnalysisExecutionPolicy,
    ConversationPolicy,
    JobExecutionPolicy,
)
from fabricassist.application.product_information import ProductInformationProvider
from fabricassist.application.vision import VisionEvidenceProvider
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.jobs.qstash_inbound import (
    DeliveryVerificationError,
    QStashDeliveryVerifier,
)
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    ConversationMessage,
)

router = APIRouter(prefix="/internal/jobs", include_in_schema=False)


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_database() -> Database:
    raise RuntimeError("Database dependency was not configured.")


async def get_storage() -> ObjectStorage:
    raise RuntimeError("Storage dependency was not configured.")


async def get_job_dispatcher() -> JobDispatcher:
    raise RuntimeError("Job dispatcher dependency was not configured.")


async def get_qstash_verifier() -> QStashDeliveryVerifier:
    raise RuntimeError("QStash verifier dependency was not configured.")


async def get_hot_cache() -> HotCache:
    raise RuntimeError("Hot-cache dependency was not configured.")


async def get_concurrency_gate() -> ConcurrencyGate:
    raise RuntimeError("Concurrency-gate dependency was not configured.")


async def get_evidence_provider() -> VisionEvidenceProvider:
    raise RuntimeError("Evidence-provider dependency was not configured.")


async def get_care_planning_provider() -> CarePlanningProvider:
    raise RuntimeError("Care-planning provider dependency was not configured.")


async def get_conversation_provider() -> ConversationProvider:
    raise RuntimeError("Conversation-provider dependency was not configured.")


async def get_product_information_provider() -> ProductInformationProvider:
    raise RuntimeError("Product-information provider dependency was not configured.")


async def get_analysis_policy() -> AnalysisExecutionPolicy:
    raise RuntimeError("Analysis policy dependency was not configured.")


async def get_job_execution_policy() -> JobExecutionPolicy:
    raise RuntimeError("Job execution policy dependency was not configured.")


async def get_conversation_policy() -> ConversationPolicy:
    raise RuntimeError("Conversation policy dependency was not configured.")


@router.post("/qstash", status_code=204)
async def execute_stage(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    database: Annotated[Database, Depends(get_database)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    verifier: Annotated[QStashDeliveryVerifier, Depends(get_qstash_verifier)],
    hot_cache: Annotated[HotCache, Depends(get_hot_cache)],
    concurrency_gate: Annotated[ConcurrencyGate, Depends(get_concurrency_gate)],
    evidence_provider: Annotated[VisionEvidenceProvider, Depends(get_evidence_provider)],
    care_planning_provider: Annotated[
        CarePlanningProvider,
        Depends(get_care_planning_provider),
    ],
    conversation_provider: Annotated[
        ConversationProvider,
        Depends(get_conversation_provider),
    ],
    product_information_provider: Annotated[
        ProductInformationProvider,
        Depends(get_product_information_provider),
    ],
    analysis_policy: Annotated[AnalysisExecutionPolicy, Depends(get_analysis_policy)],
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
            analysis_policy=analysis_policy,
            database=database,
            storage=storage,
            evidence_provider=evidence_provider,
            care_planning_provider=care_planning_provider,
            product_information_provider=product_information_provider,
            hot_cache=hot_cache,
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
    except PermanentJobMessageError:
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except TemporaryJobError:
        return Response(status_code=503)
    except PermanentJobDispatchError:
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except JobDispatchError:
        return Response(status_code=503)
    return Response(status_code=204)
