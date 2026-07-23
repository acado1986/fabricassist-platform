"""Valkey-backed distributed rate and worker concurrency limits."""
# pyright: reportArgumentType=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import time
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from fabricassist.infrastructure.telemetry import WORKER_CONCURRENCY
from fabricassist.settings import Settings


def redis_url(url: str) -> str:
    """Translate the product-facing Valkey scheme for the Redis-compatible client."""
    return url.replace("valkey://", "redis://", 1)


class LimitBackendUnavailable(RuntimeError):
    """The configured distributed limit backend could not make a decision."""


class ConcurrencyLimitExceeded(RuntimeError):
    """No provider-facing worker slot was available."""


class ValkeyRateLimiter:
    """A fixed-window limiter shared by every API replica."""

    def __init__(self, url: str) -> None:
        self._client: Redis = Redis.from_url(redis_url(url), decode_responses=True)

    async def allowed(self, bucket: str, limit: int, window_seconds: int = 60) -> bool:
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


class DistributedConcurrencyGate:
    """Lease-based global and tenant slots that recover after worker death."""

    _ACQUIRE_SCRIPT = """
    local now = tonumber(ARGV[1])
    local expires = tonumber(ARGV[2])
    local token = ARGV[3]
    local global_limit = tonumber(ARGV[4])
    local tenant_limit = tonumber(ARGV[5])
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
    redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
    if redis.call('ZCARD', KEYS[1]) >= global_limit then return 0 end
    if redis.call('ZCARD', KEYS[2]) >= tenant_limit then return 0 end
    redis.call('ZADD', KEYS[1], expires, token)
    redis.call('ZADD', KEYS[2], expires, token)
    redis.call('EXPIRE', KEYS[1], math.ceil(expires - now))
    redis.call('EXPIRE', KEYS[2], math.ceil(expires - now))
    return 1
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Redis = Redis.from_url(redis_url(settings.valkey_url), decode_responses=True)

    @asynccontextmanager
    async def slot(self, *, tenant_id: str, operation: str) -> AsyncGenerator[None, None]:
        token = str(uuid4())
        prefix = f"fabricassist:limits:v1:concurrency:{operation}"
        global_key = f"{prefix}:global"
        tenant_key = f"{prefix}:tenant:{tenant_id}"
        now = int(time())
        expires = now + self._settings.worker_concurrency_lease_seconds
        acquired = False
        try:
            decision = await self._client.eval(
                self._ACQUIRE_SCRIPT,
                2,
                global_key,
                tenant_key,
                now,
                expires,
                token,
                self._settings.worker_global_concurrency,
                self._settings.worker_tenant_concurrency,
            )
            if decision != 1:
                raise ConcurrencyLimitExceeded(operation)
            acquired = True
            WORKER_CONCURRENCY.labels(scope="global", operation=operation).inc()
            WORKER_CONCURRENCY.labels(scope="tenant", operation=operation).inc()
            yield
        except RedisError as error:
            raise LimitBackendUnavailable from error
        finally:
            try:
                if acquired:
                    await self._client.zrem(global_key, token)
                    await self._client.zrem(tenant_key, token)
            finally:
                if acquired:
                    WORKER_CONCURRENCY.labels(scope="global", operation=operation).dec()
                    WORKER_CONCURRENCY.labels(scope="tenant", operation=operation).dec()
                await self._client.aclose()
