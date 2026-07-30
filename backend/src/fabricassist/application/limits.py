"""Provider-neutral request-rate and worker-concurrency capability ports."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class LimitBackendUnavailable(RuntimeError):
    """The configured distributed backend could not make a safe decision."""


class ConcurrencyLimitExceeded(RuntimeError):
    """No provider-facing worker slot was available."""


class RateLimiter(Protocol):
    """Decide whether a versioned request bucket remains within its window."""

    async def allowed(
        self,
        bucket: str,
        limit: int,
        *,
        window_seconds: int,
    ) -> bool: ...

    async def close(self) -> None: ...


class ConcurrencyGate(Protocol):
    """Lease a global and tenant-scoped slot for one worker operation."""

    def slot(
        self,
        *,
        tenant_id: str,
        operation: str,
    ) -> AbstractAsyncContextManager[None]: ...
