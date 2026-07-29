"""Valkey fixed-window implementation of the rate-limiter port."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import RedisError

from fabricassist.application.limits import LimitBackendUnavailable
from fabricassist.infrastructure.valkey_url import redis_compatible_url


class ValkeyRateLimiterAdapter:
    """A fixed-window limiter shared by every API replica."""

    def __init__(self, url: str) -> None:
        self._client: Redis = Redis.from_url(redis_compatible_url(url), decode_responses=True)

    async def allowed(
        self,
        bucket: str,
        limit: int,
        *,
        window_seconds: int,
    ) -> bool:
        key = f"fabricassist:limits:v1:rate:{bucket}"
        try:
            count = await self._client.incr(key)
            if count == 1:
                await self._client.expire(key, window_seconds)
        except RedisError as error:
            raise LimitBackendUnavailable from error
        return int(count) <= limit

    async def close(self) -> None:
        await self._client.aclose()
