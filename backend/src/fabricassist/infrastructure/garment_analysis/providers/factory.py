"""Composition-only factory for the inactive v2 garment provider."""

from __future__ import annotations

import json
from typing import cast

from fabricassist.application.garment_analysis import GarmentVisionProvider
from fabricassist.infrastructure.garment_analysis.providers.fake import FakeGarmentVisionProvider
from fabricassist.infrastructure.garment_analysis.providers.gemini import (
    GeminiGarmentConfig,
    GeminiGarmentVisionProvider,
)
from fabricassist.infrastructure.garment_analysis.providers.openai_responses import (
    OpenAIResponsesGarmentConfig,
    OpenAIResponsesGarmentVisionProvider,
)
from fabricassist.settings import ModelCapabilityProvider, Settings


def create_garment_vision_provider(settings: Settings) -> GarmentVisionProvider:
    selected = settings.garment_analysis_provider
    if selected is ModelCapabilityProvider.MOCK:
        return FakeGarmentVisionProvider()
    if selected is ModelCapabilityProvider.GEMINI:
        return GeminiGarmentVisionProvider(
            GeminiGarmentConfig(
                api_key=settings.gemini_api_key,
                model=settings.garment_analysis_gemini_model or settings.gemini_model,
                timeout_seconds=settings.vision_timeout_seconds,
                max_output_tokens=settings.vision_max_output_tokens,
            )
        )
    if selected is ModelCapabilityProvider.OPENAI_RESPONSES:
        return OpenAIResponsesGarmentVisionProvider(
            OpenAIResponsesGarmentConfig(
                base_url=settings.openai_responses_base_url,
                api_key=settings.openai_responses_api_key,
                model=settings.garment_analysis_openai_model or settings.openai_responses_model,
                timeout_seconds=settings.vision_timeout_seconds,
                max_output_tokens=settings.vision_max_output_tokens,
                extra_headers=cast(
                    dict[str, str], json.loads(settings.openai_responses_extra_headers_json)
                ),
            )
        )
    raise ValueError(f"Unsupported garment-analysis provider: {selected}")
