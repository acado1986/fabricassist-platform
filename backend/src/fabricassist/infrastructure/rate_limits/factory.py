"""Infrastructure composition root for request rate limiting."""

from __future__ import annotations

from collections.abc import Callable

from fabricassist.application.limits import RateLimiter
from fabricassist.infrastructure.rate_limits.noop import NoOpRateLimiterAdapter
from fabricassist.infrastructure.rate_limits.valkey import ValkeyRateLimiterAdapter
from fabricassist.settings import RateLimiterBackend, Settings

RateLimiterBuilder = Callable[[Settings], RateLimiter]


def _valkey(settings: Settings) -> RateLimiter:
    return ValkeyRateLimiterAdapter(settings.valkey_url)


def _noop(_settings: Settings) -> RateLimiter:
    return NoOpRateLimiterAdapter()


RATE_LIMITER_ADAPTERS: dict[RateLimiterBackend, RateLimiterBuilder] = {
    RateLimiterBackend.VALKEY: _valkey,
    RateLimiterBackend.NOOP: _noop,
}


def create_rate_limiter(settings: Settings) -> RateLimiter:
    """Select one registered rate-limiter strategy."""
    try:
        builder = RATE_LIMITER_ADAPTERS[settings.rate_limiter_backend]
    except KeyError as error:  # pragma: no cover
        raise ValueError(
            f"Unsupported rate-limiter backend: {settings.rate_limiter_backend}"
        ) from error
    return builder(settings)
