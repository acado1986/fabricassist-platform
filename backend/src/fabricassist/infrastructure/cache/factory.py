"""Infrastructure composition root for the hot-cache capability."""

from __future__ import annotations

from collections.abc import Callable

from fabricassist.application.cache import HotCache
from fabricassist.infrastructure.cache.noop import NoOpHotCacheAdapter
from fabricassist.infrastructure.cache.valkey import ValkeyHotCacheAdapter
from fabricassist.settings import HotCacheBackend, Settings

HotCacheBuilder = Callable[[Settings], HotCache]


def _valkey(settings: Settings) -> HotCache:
    return ValkeyHotCacheAdapter(settings.valkey_url)


def _noop(_settings: Settings) -> HotCache:
    return NoOpHotCacheAdapter()


HOT_CACHE_ADAPTERS: dict[HotCacheBackend, HotCacheBuilder] = {
    HotCacheBackend.VALKEY: _valkey,
    HotCacheBackend.NOOP: _noop,
}


def create_hot_cache(settings: Settings) -> HotCache:
    """Select one registered hot-cache strategy from typed environment settings."""
    try:
        builder = HOT_CACHE_ADAPTERS[settings.hot_cache_backend]
    except KeyError as error:  # pragma: no cover - enum validation prevents this
        raise ValueError(f"Unsupported hot-cache backend: {settings.hot_cache_backend}") from error
    return builder(settings)
