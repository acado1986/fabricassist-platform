"""Run one scheduler-independent FabricAssist retention pass."""

from __future__ import annotations

import asyncio

from fabricassist.application.lifecycle import run_retention_once
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.storage.factory import create_object_storage
from fabricassist.settings import Settings


async def run() -> tuple[int, int]:
    settings = Settings()
    database = Database.from_settings(settings)
    try:
        async with database.session_factory() as session:
            return await run_retention_once(
                session,
                create_object_storage(settings),
                merged_garment_retention_days=settings.merged_garment_retention_days,
                batch_size=settings.publication_recovery_batch_size,
                max_deletion_attempts=settings.deletion_max_attempts,
            )
    finally:
        await database.close()


def main() -> None:
    merged, deleted = asyncio.run(run())
    print(f"Retention pass completed: merged_garments={merged}, objects_deleted={deleted}.")


if __name__ == "__main__":
    main()
