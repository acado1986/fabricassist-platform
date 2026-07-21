"""SQLAlchemy wiring used only for connectivity at this phase."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalise_database_url(database_url: str) -> str:
    """Use psycopg's async SQLAlchemy dialect for a PostgreSQL connection URL."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


class DatabasePort(Protocol):
    """Database capability required by the Phase 2 API composition root."""

    async def is_available(self) -> bool: ...

    async def close(self) -> None: ...


class Database:
    """Database engine and session factory; no schema is defined in Phase 2."""

    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            normalise_database_url(database_url), pool_pre_ping=True
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def is_available(self) -> bool:
        """Run a safe connectivity probe without querying business data."""
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    async def close(self) -> None:
        """Release database connections during application shutdown."""
        await self.engine.dispose()
