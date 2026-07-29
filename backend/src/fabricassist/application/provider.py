"""Shared non-secret metadata for independent model capabilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderDescriptor:
    provider: str
    model: str
