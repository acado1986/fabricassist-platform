"""Explicit no-op implementation for deployments without a hot cache."""

from __future__ import annotations


class NoOpHotCacheAdapter:
    """Always miss and discard writes without weakening durable PostgreSQL data."""

    async def get_json(self, key: str) -> dict[str, object] | None:
        del key
        return None

    async def set_json(
        self,
        key: str,
        value: dict[str, object],
        *,
        ttl_seconds: int,
    ) -> None:
        del key, value, ttl_seconds
