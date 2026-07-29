from __future__ import annotations

import json
from typing import cast
from uuid import uuid4

import pytest
from google.genai import types

from fabricassist.application.model_provider import (
    DEFAULT_EVIDENCE_SYSTEM_PROMPT,
    ModelProviderPrompts,
)
from fabricassist.application.vision import NormalizedImage, VisionProviderError
from fabricassist.domain.conversations import ConversationContext
from fabricassist.domain.evidence import ImageRole
from fabricassist.infrastructure.vision.providers import (
    GeminiAdapterConfig,
    GeminiProviderAdapter,
    build_model_provider,
)
from fabricassist.infrastructure.vision.providers.gemini import GEMINI_PROVIDER_PROMPTS
from fabricassist.settings import Settings


def _config(*, prompts: ModelProviderPrompts | None = None) -> GeminiAdapterConfig:
    return GeminiAdapterConfig(
        api_key="synthetic-test-key",
        model="gemini-2.5-flash",
        timeout_seconds=120,
        max_output_tokens=16_000,
        prompts=prompts or ModelProviderPrompts(),
    )


def _response(
    payload: dict[str, object], *, input_tokens: int = 123, output_tokens: int = 45
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse.model_validate(
        {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": json.dumps(payload)}],
                    }
                }
            ],
            "usage_metadata": {
                "prompt_token_count": input_tokens,
                "candidates_token_count": output_tokens,
            },
        }
    )


@pytest.mark.asyncio
async def test_gemini_provider_sends_image_bytes_and_validates_evidence() -> None:
    image_id = uuid4()
    observed: dict[str, object] = {}

    async def generate(
        model: str, contents: object, config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        observed.update(model=model, contents=contents, config=config)
        return _response(
            {
                "observations": [
                    {
                        "id": str(uuid4()),
                        "kind": "label_text",
                        "value": "Machine wash 30°C",
                        "confidence": 96,
                        "source": {
                            "image_id": str(image_id),
                            "role": "care_label",
                        },
                        "time_varying": False,
                    }
                ],
                "care_facts": [
                    {
                        "code": "machine_wash",
                        "permission": "allowed",
                        "temperature_c": 30,
                        "confidence": 96,
                        "source": {
                            "image_id": str(image_id),
                            "role": "care_label",
                        },
                        "original_text": "Machine wash 30°C",
                    }
                ],
                "uncertainties": [],
            }
        )

    provider = GeminiProviderAdapter(_config(), generate_content=generate)
    result = await provider.extract_evidence(
        (
            NormalizedImage(
                image_id=image_id,
                jpeg_bytes=b"jpeg-bytes",
                sha256="0" * 64,
                width=640,
                height=640,
                role=ImageRole.CARE_LABEL,
            ),
        )
    )

    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash"
    assert result.input_tokens == 123
    assert result.output_tokens == 45
    assert result.delta.care_facts[0].temperature_c == 30
    parts = cast(list[types.Part], observed["contents"])
    assert parts[0].text == f"Image ID: {image_id}; declared role: care_label."
    assert parts[1].inline_data is not None
    assert parts[1].inline_data.data == b"jpeg-bytes"
    config = cast(types.GenerateContentConfig, observed["config"])
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == result.delta.__class__.model_json_schema()


@pytest.mark.asyncio
async def test_gemini_provider_rejects_unknown_source_image() -> None:
    async def generate(
        model: str, contents: object, config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        _ = (model, contents, config)
        return _response(
            {
                "observations": [
                    {
                        "id": str(uuid4()),
                        "kind": "label_text",
                        "value": "Unknown source",
                        "confidence": 90,
                        "source": {
                            "image_id": str(uuid4()),
                            "role": "care_label",
                        },
                        "time_varying": False,
                    }
                ],
                "care_facts": [],
                "uncertainties": [],
            }
        )

    provider = GeminiProviderAdapter(_config(), generate_content=generate)
    with pytest.raises(VisionProviderError, match="invalid structured evidence") as error:
        await provider.extract_evidence(
            (
                NormalizedImage(
                    image_id=uuid4(),
                    jpeg_bytes=b"jpeg-bytes",
                    sha256="0" * 64,
                    width=640,
                    height=640,
                    role=ImageRole.CARE_LABEL,
                ),
            )
        )

    assert error.value.code == "PROVIDER_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_gemini_conversation_returns_typed_proposal() -> None:
    async def generate(
        model: str, contents: object, config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        _ = (model, contents, config)
        return _response(
            {
                "text": "Upload a clear care-label photo before choosing a wash cycle.",
                "actionable_claims": [],
                "evidence_ids": [],
                "uncertainties": ["care_label_missing"],
                "follow_up_questions": ["Can you add the care label?"],
            },
            input_tokens=20,
            output_tokens=10,
        )

    provider = GeminiProviderAdapter(_config(), generate_content=generate)
    result = await provider.answer(
        ConversationContext(
            garment_id=uuid4(),
            analysis_revision_id=uuid4(),
            dossier={},
            validated_plan={},
            validation={},
        ),
        "Can I wash this?",
    )

    assert result.provider == "gemini"
    assert result.proposal.actionable_claims == []
    assert result.input_tokens == 20
    assert result.output_tokens == 10


def test_factory_selects_one_complete_credential_owning_adapter() -> None:
    settings = Settings(
        environment="test",
        vision_provider="gemini",
        gemini_api_key="synthetic-test-key",
        gemini_model="gemini-2.5-flash",
    )

    adapter = build_model_provider(settings)

    assert isinstance(adapter, GeminiProviderAdapter)
    assert callable(adapter.extract_evidence)
    assert callable(adapter.answer)
    assert "synthetic-test-key" not in repr(_config())


def test_provider_prompts_have_safe_defaults_and_gemini_specialization() -> None:
    assert ModelProviderPrompts().evidence_system == DEFAULT_EVIDENCE_SYSTEM_PROMPT
    assert GEMINI_PROVIDER_PROMPTS.evidence_system.startswith(DEFAULT_EVIDENCE_SYSTEM_PROMPT)
    assert "Analyze the complete image set" in GEMINI_PROVIDER_PROMPTS.evidence_system
    assert "Gemini" not in GEMINI_PROVIDER_PROMPTS.evidence_system
