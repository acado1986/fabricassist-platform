"""Bounded autonomous recovery for committed external-publication intents."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from uuid import UUID

from fabricassist.application.job_execution import (
    reconcile_unpublished_conversations,
    reconcile_unpublished_operations,
)
from fabricassist.application.jobs import JobDispatcher
from fabricassist.application.lifecycle import process_object_deletions
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.infrastructure.database import Database

logger = logging.getLogger(__name__)
SYSTEM_RECOVERY_CORRELATION_ID = str(UUID(int=0))


async def recover_publications_once(
    *,
    database: Database,
    dispatcher: JobDispatcher,
    batch_size: int,
) -> tuple[int, int]:
    """Recover one bounded batch from each PostgreSQL outbox."""
    async with database.session_factory() as session:
        analysis = await reconcile_unpublished_operations(
            session=session,
            dispatcher=dispatcher,
            correlation_id=SYSTEM_RECOVERY_CORRELATION_ID,
            limit=batch_size,
        )
    async with database.session_factory() as session:
        conversations = await reconcile_unpublished_conversations(
            session=session,
            dispatcher=dispatcher,
            limit=batch_size,
        )
    return analysis, conversations


async def publication_recovery_loop(
    *,
    database: Database,
    dispatcher: JobDispatcher,
    storage: ObjectStorage,
    interval_seconds: int,
    batch_size: int,
    deletion_max_attempts: int,
) -> None:
    """Run publication and object-deletion recovery until the API shuts down."""
    while True:
        try:
            analysis, conversations = await recover_publications_once(
                database=database,
                dispatcher=dispatcher,
                batch_size=batch_size,
            )
            async with database.session_factory() as session:
                deletions = await process_object_deletions(
                    session,
                    storage,
                    limit=batch_size,
                    max_attempts=deletion_max_attempts,
                )
            if analysis or conversations or deletions:
                logger.info(
                    "Recovered durable external operations",
                    extra={
                        "analysis_publications": analysis,
                        "conversation_publications": conversations,
                        "object_deletions": deletions,
                    },
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            # The database remains authoritative and the next bounded pass retries.
            # No destination URL, message payload, or credentials are logged.
            logger.exception("Durable publication recovery pass failed")
        await asyncio.sleep(interval_seconds)


async def stop_recovery_task(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
