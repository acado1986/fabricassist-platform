"""Explicit no-op rate limiter for non-production topologies."""

from __future__ import annotations


class NoOpRateLimiterAdapter:
    """Allow every request; production settings reject this adapter."""

    async def allowed(
        self,
        bucket: str,
        limit: int,
        *,
        window_seconds: int,
    ) -> bool:
        del bucket, limit, window_seconds
        return True

    async def close(self) -> None:
        return None
