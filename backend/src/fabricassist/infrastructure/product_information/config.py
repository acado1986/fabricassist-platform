"""Typed concrete product-information adapter configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HttpJsonProductInformationConfig:
    base_url: str
    allowed_hosts: frozenset[str]
    timeout_seconds: int
    max_response_bytes: int
    api_key: str = field(default="", repr=False)
