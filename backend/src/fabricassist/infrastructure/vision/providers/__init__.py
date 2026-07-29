"""Composition root for model-provider adapters."""

from __future__ import annotations

import json
from typing import cast

from fabricassist.application.model_provider import ModelProvider
from fabricassist.infrastructure.vision.providers.gemini import (
    GEMINI_PROVIDER_PROMPTS,
    GeminiAdapterConfig,
    GeminiProviderAdapter,
)
from fabricassist.infrastructure.vision.providers.mock import MockModelProviderAdapter
from fabricassist.infrastructure.vision.providers.openai_responses import (
    OpenAIResponsesAdapterConfig,
    OpenAIResponsesProviderAdapter,
)
from fabricassist.settings import Settings


def build_model_provider(settings: Settings) -> ModelProvider:
    """Translate runtime settings into one credential-owning adapter.

    This is the only module that knows both application settings and concrete
    adapters. Application services receive the `ModelProvider` interface and do
    not know which SDK, credentials, endpoint, or specialized prompt is active.
    """
    if settings.vision_provider == "mock":
        return MockModelProviderAdapter()
    if settings.vision_provider == "gemini":
        return GeminiProviderAdapter(
            GeminiAdapterConfig(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.vision_timeout_seconds,
                max_output_tokens=settings.vision_max_output_tokens,
                prompts=GEMINI_PROVIDER_PROMPTS,
            )
        )
    if settings.vision_provider == "openai_responses":
        return OpenAIResponsesProviderAdapter(
            OpenAIResponsesAdapterConfig(
                base_url=settings.vision_base_url,
                api_key=settings.vision_api_key,
                model=settings.vision_model,
                timeout_seconds=settings.vision_timeout_seconds,
                extra_headers=cast(dict[str, str], json.loads(settings.vision_extra_headers_json)),
                max_output_tokens=settings.vision_max_output_tokens,
            )
        )
    raise RuntimeError(f"Model provider {settings.vision_provider!r} is not implemented")


__all__ = [
    "GeminiAdapterConfig",
    "GeminiProviderAdapter",
    "OpenAIResponsesAdapterConfig",
    "OpenAIResponsesProviderAdapter",
    "build_model_provider",
]
