"""Celery task entry points, intentionally thin around application orchestration."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import asyncio
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from celery import shared_task

from fabricassist.api.logging import correlation_id_context, log_context
from fabricassist.application.analysis import analyse_scan
from fabricassist.application.conversations import answer_message_by_id
from fabricassist.application.lifecycle import (
    enqueue_deletion,
    process_object_deletions,
    retention_candidates,
)
from fabricassist.application.vision import VisionProviderError
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.limits import (
    ConcurrencyLimitExceeded,
    DistributedConcurrencyGate,
    LimitBackendUnavailable,
)
from fabricassist.infrastructure.persistence.models import ConversationMessage, Scan
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.infrastructure.telemetry import measure_job
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


async def _run_analysis_with_limit(
    database: Database, storage: S3Storage, settings: Settings, scan_id: UUID
) -> None:
    async with database.session_factory() as session:
        scan = await session.get(Scan, scan_id)
        tenant_id = str(scan.tenant_id) if scan is not None else "missing"
    async with DistributedConcurrencyGate(settings).slot(tenant_id=tenant_id, operation="analysis"):
        await analyse_scan(
            database=database,
            storage=storage,
            settings=settings,
            scan_id=scan_id,
        )


async def _run_message_with_limit(database: Database, settings: Settings, message_id: UUID) -> None:
    async with database.session_factory() as session:
        message = await session.get(ConversationMessage, message_id)
        tenant_id = str(message.tenant_id) if message is not None else "missing"
    async with DistributedConcurrencyGate(settings).slot(
        tenant_id=tenant_id, operation="conversation"
    ):
        await answer_message_by_id(database, message_id, settings)


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


@shared_task(name="fabricassist.analyse_scan", bind=True, autoretry_for=(), max_retries=3)
def analyse_scan_task(self: Any, scan_id: str) -> None:
    """Execute one idempotent scan operation without holding an API request open."""
    settings = Settings()
    database = Database(settings.database_url)
    try:
        with _task_log_context(self, operation="analysis", resource_id=scan_id):
            with measure_job("analysis"):
                asyncio.run(
                    _run_analysis_with_limit(database, S3Storage(settings), settings, UUID(scan_id))
                )
    except (ConcurrencyLimitExceeded, LimitBackendUnavailable) as error:
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
    database = Database(settings.database_url)
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
    database = Database(settings.database_url)

    async def run() -> None:
        async with database.session_factory() as session:
            for image in await retention_candidates(session):
                await enqueue_deletion(
                    session,
                    tenant_id=image.tenant_id,
                    user_id=None,
                    resource_type="scan",
                    resource_id=image.scan_id,
                    images=[image],
                )
            await session.commit()
            await process_object_deletions(session, S3Storage(settings))

    try:
        with _task_log_context(self, operation="retention", resource_id="retention"):
            with measure_job("retention"):
                asyncio.run(run())
    finally:
        asyncio.run(database.close())
