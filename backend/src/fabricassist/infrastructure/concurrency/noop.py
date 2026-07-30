"""Explicit no-op concurrency gate for externally bounded deployments."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class NoOpConcurrencyGateAdapter:
    """Yield immediately; production settings reject this adapter."""

    @asynccontextmanager
    async def slot(self, *, tenant_id: str, operation: str) -> AsyncGenerator[None, None]:
        del tenant_id, operation
        yield
