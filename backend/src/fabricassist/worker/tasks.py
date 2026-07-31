"""Celery task entry points, intentionally thin around application orchestration."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import asyncio
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from fabricassist.api.logging import correlation_id_context, log_context
from fabricassist.application.conversations import answer_message_by_id
from fabricassist.application.job_execution import TemporaryJobError, execute_checkpoint
from fabricassist.application.job_orchestration import publish_operation
from fabricassist.application.jobs import AnalysisJobMessage
from fabricassist.application.lifecycle import (
    run_retention_once,
)
from fabricassist.application.limits import (
    ConcurrencyLimitExceeded,
    LimitBackendUnavailable,
)
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.application.policies import (
    AnalysisExecutionPolicy,
    ConversationPolicy,
    JobExecutionPolicy,
)
from fabricassist.application.vision import VisionProviderError
from fabricassist.infrastructure.cache.factory import create_hot_cache
from fabricassist.infrastructure.concurrency.factory import create_concurrency_gate
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.jobs.factory import create_job_dispatcher
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    ConversationMessage,
    Scan,
)
from fabricassist.infrastructure.product_information.factory import (
    create_product_information_provider,
)
from fabricassist.infrastructure.storage.factory import create_object_storage
from fabricassist.infrastructure.telemetry import measure_job
from fabricassist.infrastructure.vision.providers import (
    create_care_planning_provider,
    create_conversation_provider,
    create_evidence_provider,
)
from fabricassist.settings import Settings


@contextmanager
def _task_log_context(
    task: Any, *, operation: str, resource_id: str
) -> Generator[None, None, None]:
    raw_headers: object = getattr(task.request, "headers", None)
    headers: Mapping[str, object] = raw_headers if isinstance(raw_headers, Mapping) else {}
    correlation_id = str(headers.get("correlation_id") or UUID(int=0))
    token = correlation_id_context.set(correlation_id)
    try:
        with log_context(
            service="fabricassist-worker",
            job_id=str(getattr(task.request, "id", "")),
            stage=operation,
            resource_id=resource_id,
        ):
            yield
    finally:
        correlation_id_context.reset(token)


async def _execute_analysis_job(
    database: Database,
    storage: ObjectStorage,
    settings: Settings,
    message: AnalysisJobMessage,
) -> None:
    async with database.session_factory() as session:
        result = await execute_checkpoint(
            session=session,
            message=message,
            database=database,
            storage=storage,
            execution_policy=JobExecutionPolicy(
                stage_budget_seconds=settings.job_stage_budget_seconds
            ),
            analysis_policy=AnalysisExecutionPolicy(
                hot_cache_ttl_seconds=settings.cache_hot_ttl_seconds,
                product_cache_minutes=settings.product_cache_minutes,
            ),
            evidence_provider=create_evidence_provider(settings),
            care_planning_provider=create_care_planning_provider(settings),
            product_information_provider=create_product_information_provider(settings),
            hot_cache=create_hot_cache(settings),
            concurrency_gate=create_concurrency_gate(settings),
        )
        if result.continuation is None:
            return
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
                dispatcher=create_job_dispatcher(settings),
            )


async def _run_message_with_limit(database: Database, settings: Settings, message_id: UUID) -> None:
    async with database.session_factory() as session:
        message = await session.get(ConversationMessage, message_id)
        tenant_id = str(message.tenant_id) if message is not None else "missing"
    async with create_concurrency_gate(settings).slot(
        tenant_id=tenant_id, operation="conversation"
    ):
        await answer_message_by_id(
            database,
            message_id,
            create_conversation_provider(settings),
            ConversationPolicy(
                recent_message_limit=settings.conversation_recent_message_limit,
                relevant_image_limit=settings.conversation_relevant_image_limit,
            ),
        )


async def _mark_analysis_failed(database: Database, scan_id: UUID, error_code: str) -> None:
    """Persist terminal worker errors so a client never polls a stale queued scan."""
    async with database.session_factory() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None or scan.status in {"completed", "deleted"}:
            return
        scan.status = "failed"
        scan.analysis_stage = "failed"
        scan.analysis_error_code = error_code
        scan.progress_percent = 100
        await session.commit()


@shared_task(
    name="fabricassist.execute_analysis_job",
    bind=True,
    autoretry_for=(),
    max_retries=3,
)
def execute_analysis_job_task(self: Any, payload: str) -> None:
    """Execute one idempotent scan operation without holding an API request open."""
    settings = Settings()
    database = Database.from_settings(settings)
    message = AnalysisJobMessage.model_validate_json(payload)
    scan_id = str(message.scan_id)
    try:
        with _task_log_context(self, operation="analysis", resource_id=scan_id):
            with measure_job("analysis"):
                asyncio.run(
                    _execute_analysis_job(
                        database,
                        create_object_storage(settings),
                        settings,
                        message,
                    )
                )
    except (
        ConcurrencyLimitExceeded,
        LimitBackendUnavailable,
        TemporaryJobError,
    ) as error:
        raise self.retry(exc=error, countdown=30) from error
    except VisionProviderError as error:
        asyncio.run(_mark_analysis_failed(database, UUID(scan_id), error.code))
        raise
    except Exception:
        asyncio.run(_mark_analysis_failed(database, UUID(scan_id), "ANALYSIS_INTERNAL_ERROR"))
        raise
    finally:
        asyncio.run(database.close())


@shared_task(name="fabricassist.answer_message", bind=True, autoretry_for=(), max_retries=3)
def answer_message_task(self: Any, message_id: str) -> None:
    settings = Settings()
    database = Database.from_settings(settings)
    try:
        with _task_log_context(self, operation="conversation", resource_id=message_id):
            with measure_job("conversation"):
                asyncio.run(_run_message_with_limit(database, settings, UUID(message_id)))
    except (ConcurrencyLimitExceeded, LimitBackendUnavailable) as error:
        raise self.retry(exc=error, countdown=30) from error
    finally:
        asyncio.run(database.close())


@shared_task(name="fabricassist.process_retention", bind=True, autoretry_for=(), max_retries=3)
def process_retention_task(self: Any) -> None:
    """Queue expired originals then retry private-object deletion from the DB outbox."""
    settings = Settings()
    database = Database.from_settings(settings)

    async def run() -> None:
        async with database.session_factory() as session:
            await run_retention_once(
                session,
                create_object_storage(settings),
                merged_garment_retention_days=settings.merged_garment_retention_days,
                batch_size=settings.publication_recovery_batch_size,
                max_deletion_attempts=settings.deletion_max_attempts,
            )

    try:
        with _task_log_context(self, operation="retention", resource_id="retention"):
            with measure_job("retention"):
                asyncio.run(run())
    finally:
        asyncio.run(database.close())
