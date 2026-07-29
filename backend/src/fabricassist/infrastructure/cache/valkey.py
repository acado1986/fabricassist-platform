"""Best-effort Valkey implementation of the hot-cache port."""

from __future__ import annotations

import json
from typing import Any, cast

from redis import asyncio as redis

from fabricassist.infrastructure.valkey_url import redis_compatible_url


class ValkeyHotCacheAdapter:
    """A cache outage is deliberately indistinguishable from a miss."""

    def __init__(self, url: str) -> None:
        client_factory: Any = cast(Any, redis).from_url
        self._client: Any = client_factory(redis_compatible_url(url), decode_responses=True)

    async def get_json(self, key: str) -> dict[str, object] | None:
        try:
            value = await self._client.get(key)
            parsed = json.loads(value) if value else None
            return cast(dict[str, object], parsed) if isinstance(parsed, dict) else None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    async def set_json(
        self,
        key: str,
        value: dict[str, object],
        *,
        ttl_seconds: int,
    ) -> None:
        try:
            await self._client.set(key, json.dumps(value, sort_keys=True), ex=ttl_seconds)
        except redis.RedisError:
            return
