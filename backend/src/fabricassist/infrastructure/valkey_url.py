"""Pure Redis-compatible URL normalization shared by Valkey adapters."""


def redis_compatible_url(url: str) -> str:
    return url.replace("valkey://", "redis://", 1)
