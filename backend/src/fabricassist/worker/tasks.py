"""Celery task entry points, intentionally thin around application orchestration."""
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import asyncio
from uuid import UUID

from celery import shared_task

from fabricassist.application.analysis import analyse_scan
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
