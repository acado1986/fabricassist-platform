"""Best-effort Valkey hot mirror with bounded failures."""

from __future__ import annotations

import json
from typing import Any

from redis import asyncio as redis


class ValkeyHotMirror:
    """A cache outage is deliberately indistinguishable from a miss."""

    def __init__(self, url: str, enabled: bool) -> None:
        self._client = redis.from_url(url, decode_responses=True) if enabled else None

    async def get_json(self, key: str) -> dict[str, Any] | None:
        if self._client is None:
            return None
        try:
            value = await self._client.get(key)
            parsed = json.loads(value) if value else None
            return parsed if isinstance(parsed, dict) else None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if self._client is None:
            return
        try:
            await self._client.set(key, json.dumps(value, sort_keys=True), ex=ttl_seconds)
        except redis.RedisError:
            return
