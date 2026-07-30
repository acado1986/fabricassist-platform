"""SQLAlchemy wiring used only for connectivity at this phase."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from fabricassist.settings import Settings


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

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle_seconds: int = -1,
        connect_attempts: int = 1,
        connect_retry_seconds: float = 0,
    ) -> None:
        self.engine: AsyncEngine = create_async_engine(
            normalise_database_url(database_url),
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle_seconds,
        )
        self._connect_attempts = connect_attempts
        self._connect_retry_seconds = connect_retry_seconds
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        """Build the single runtime engine from composition-root configuration."""
        return cls(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle_seconds=settings.database_pool_recycle_seconds,
            connect_attempts=settings.database_connect_attempts,
            connect_retry_seconds=settings.database_connect_retry_seconds,
        )

    async def is_available(self) -> bool:
        """Run a safe connectivity probe without querying business data."""
        for attempt in range(self._connect_attempts):
            try:
                async with self.engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
            except SQLAlchemyError:
                if attempt + 1 == self._connect_attempts:
                    return False
                await asyncio.sleep(self._connect_retry_seconds)
            else:
                return True
        return False

    async def close(self) -> None:
        """Release database connections during application shutdown."""
        await self.engine.dispose()
