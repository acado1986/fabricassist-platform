from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from fabricassist.infrastructure.database import Database, normalise_database_url
from fabricassist.settings import Settings


def test_postgresql_url_uses_psycopg_dialect() -> None:
    assert normalise_database_url("postgresql://localhost/fabricassist") == (
        "postgresql+psycopg://localhost/fabricassist"
    )


def test_alpha_database_uses_bounded_pool_settings() -> None:
    settings = Settings(environment="test")
    database = Database(
        settings.database_url,
        pool_size=2,
        max_overflow=1,
        pool_recycle_seconds=300,
    )

    pool = cast(Any, database.engine.pool)
    assert pool.size() == 2
    assert pool._max_overflow == 1  # noqa: SLF001
    assert pool._recycle == 300  # noqa: SLF001


@pytest.mark.asyncio
async def test_database_retries_a_transient_readiness_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database("postgresql://localhost/fabricassist", connect_attempts=2)
    calls = 0

    class FailedConnection:
        async def __aenter__(self) -> FailedConnection:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OperationalError("SELECT 1", {}, RuntimeError("cold start"))
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def execute(self, _statement: object) -> None:
            return None

    def connect(_engine: AsyncEngine) -> FailedConnection:
        return FailedConnection()

    monkeypatch.setattr(AsyncEngine, "connect", connect)

    assert await database.is_available()
    assert calls == 2
    await database.close()
