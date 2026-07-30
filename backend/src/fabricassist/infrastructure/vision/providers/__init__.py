"""Independent model-capability factories."""

from __future__ import annotations

import json
from typing import cast

from fabricassist.application.conversation_provider import ConversationProvider
from fabricassist.application.planning import CarePlanningProvider
from fabricassist.application.vision import VisionEvidenceProvider
from fabricassist.infrastructure.vision.providers.gemini import (
    GEMINI_PROVIDER_PROMPTS,
    GeminiAdapterConfig,
    GeminiProviderAdapter,
)
from fabricassist.infrastructure.vision.providers.mock import MockModelCapabilityAdapter
from fabricassist.infrastructure.vision.providers.openai_responses import (
    OpenAIResponsesAdapterConfig,
    OpenAIResponsesProviderAdapter,
)
from fabricassist.settings import ModelCapabilityProvider, Settings


def _construct(
    selected: ModelCapabilityProvider,
    settings: Settings,
) -> MockModelCapabilityAdapter | GeminiProviderAdapter | OpenAIResponsesProviderAdapter:
    if selected is ModelCapabilityProvider.MOCK:
        return MockModelCapabilityAdapter()
    if selected is ModelCapabilityProvider.GEMINI:
        return GeminiProviderAdapter(
            GeminiAdapterConfig(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.vision_timeout_seconds,
                max_output_tokens=settings.vision_max_output_tokens,
                debug_logging=settings.vision_debug_logging,
                prompts=GEMINI_PROVIDER_PROMPTS,
            )
        )
    if selected is ModelCapabilityProvider.OPENAI_RESPONSES:
        return OpenAIResponsesProviderAdapter(
            OpenAIResponsesAdapterConfig(
                base_url=settings.openai_responses_base_url,
                api_key=settings.openai_responses_api_key,
                model=settings.openai_responses_model,
                timeout_seconds=settings.vision_timeout_seconds,
                extra_headers=cast(
                    dict[str, str],
                    json.loads(settings.openai_responses_extra_headers_json),
                ),
                max_output_tokens=settings.vision_max_output_tokens,
                debug_logging=settings.vision_debug_logging,
            )
        )
    raise ValueError(f"Unsupported model capability provider: {selected}")


def create_evidence_provider(settings: Settings) -> VisionEvidenceProvider:
    return _construct(settings.evidence_provider, settings)


def create_care_planning_provider(settings: Settings) -> CarePlanningProvider:
    return _construct(settings.care_planner_provider, settings)


def create_conversation_provider(settings: Settings) -> ConversationProvider:
    return _construct(settings.chat_provider, settings)


__all__ = [
    "GeminiAdapterConfig",
    "GeminiProviderAdapter",
    "OpenAIResponsesAdapterConfig",
    "OpenAIResponsesProviderAdapter",
    "create_care_planning_provider",
    "create_conversation_provider",
    "create_evidence_provider",
]
