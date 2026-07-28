"""Protected live smoke for a dedicated Neon database; never enabled by default."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from fabricassist.infrastructure.database import Database, normalise_database_url

pytestmark = pytest.mark.integration


def required_url(name: str) -> str:
    if os.environ.get("FABRICASSIST_NEON_SMOKE") != "1":
        pytest.skip("Neon smoke is enabled only by make test-neon.")
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"{name} is required for the enabled Neon smoke.")
    if "sslmode=require" not in value:
        pytest.fail(f"{name} must require TLS.")
    return value


@pytest.mark.asyncio
async def test_neon_runtime_pool_and_direct_migration_urls() -> None:
    runtime_url = required_url("FABRICASSIST_NEON_RUNTIME_URL")
    migration_url = required_url("FABRICASSIST_NEON_MIGRATION_URL")
    database = Database(
        runtime_url,
        pool_size=2,
        max_overflow=1,
        pool_recycle_seconds=300,
        connect_attempts=3,
        connect_retry_seconds=1,
    )
    assert await database.is_available()
    await database.close()

    engine = create_engine(normalise_database_url(migration_url), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            extensions = set(connection.scalars(text("SELECT extname FROM pg_extension")))
        assert {"citext", "vector"} <= extensions
    finally:
        engine.dispose()
