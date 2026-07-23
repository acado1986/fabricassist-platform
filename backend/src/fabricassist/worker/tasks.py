"""Celery task entry points, intentionally thin around application orchestration."""
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import asyncio
from uuid import UUID

from celery import shared_task

from fabricassist.application.analysis import analyse_scan
from fabricassist.application.conversations import answer_message_by_id
from fabricassist.application.lifecycle import (
    enqueue_deletion,
    process_object_deletions,
    retention_candidates,
)
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import Settings


@shared_task(name="fabricassist.analyse_scan", bind=True, autoretry_for=(), max_retries=3)
def analyse_scan_task(self: object, scan_id: str) -> None:
    """Execute one idempotent scan operation without holding an API request open."""
    _ = self
    settings = Settings()
    database = Database(settings.database_url)
    try:
        asyncio.run(
            analyse_scan(
                database=database,
                storage=S3Storage(settings),
                settings=settings,
                scan_id=UUID(scan_id),
            )
        )
    finally:
        asyncio.run(database.close())


@shared_task(name="fabricassist.answer_message", bind=True, autoretry_for=(), max_retries=3)
def answer_message_task(self: object, message_id: str) -> None:
    _ = self
    settings = Settings()
    database = Database(settings.database_url)
    try:
        asyncio.run(answer_message_by_id(database, UUID(message_id)))
    finally:
        asyncio.run(database.close())


@shared_task(name="fabricassist.process_retention", bind=True, autoretry_for=(), max_retries=3)
def process_retention_task(self: object) -> None:
    """Queue expired originals then retry private-object deletion from the DB outbox."""
    _ = self
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
        asyncio.run(run())
    finally:
        asyncio.run(database.close())
