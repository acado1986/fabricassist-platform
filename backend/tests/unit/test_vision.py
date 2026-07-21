from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from fabricassist.application.vision import PROMPT_VERSION, LabelExtractionPayload
from fabricassist.infrastructure.vision.providers import (
    CARE_LABEL_SYSTEM_PROMPT,
    AzureOpenAIVisionProvider,
    MockVisionProvider,
    OpenAIResponsesVisionProvider,
    get_vision_provider,
)
from fabricassist.settings import Settings


def test_prohibited_wash_cannot_include_a_temperature() -> None:
    with pytest.raises(ValidationError):
        LabelExtractionPayload(
            image_type="care_label",
            wash_permission="prohibited",
            max_wash_temperature_c=30,
            overall_confidence=90,
        )


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic_and_review_safe() -> None:
    from fabricassist.application.vision import NormalizedImage

    result = await MockVisionProvider().extract_label(
        (
            NormalizedImage(
                jpeg_bytes=b"garment", sha256="0" * 64, width=320, height=320, kind="garment"
            ),
            NormalizedImage(
                jpeg_bytes=b"label",
                sha256="1" * 64,
                width=320,
                height=320,
                kind="care_label",
            ),
        )
    )

    assert result.provider == "mock"
    assert result.payload.overall_confidence == 0


def test_azure_provider_uses_deployment_endpoint_and_api_version() -> None:
    provider = AzureOpenAIVisionProvider(
        Settings(
            vision_provider="azure_openai",
            azure_openai_endpoint="https://example.openai.azure.com/",
            azure_openai_api_key="not-a-real-key",
            azure_openai_deployment="vision deployment",
        )
    )

    assert provider.endpoint_url() == (
        "https://example.openai.azure.com/openai/deployments/vision%20deployment/"
        "chat/completions?api-version=2024-10-21"
    )


def test_provider_registry_keeps_worker_contract_vendor_neutral() -> None:
    provider = get_vision_provider(
        Settings(
            vision_provider="azure_openai",
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_api_key="not-a-real-key",
            azure_openai_deployment="vision",
        )
    )

    assert isinstance(provider, AzureOpenAIVisionProvider)


def test_generic_responses_adapter_supports_proxy_headers() -> None:
    provider = get_vision_provider(
        Settings(
            vision_provider="openai_responses",
            vision_base_url="https://gateway.example/openai/v1",
            vision_api_key="not-a-real-key",
            vision_model="vision-mini",
            vision_extra_headers_json='{"X-Gateway-Key":"not-a-real-key"}',
        )
    )

    assert isinstance(provider, OpenAIResponsesVisionProvider)
    assert provider.endpoint_url() == "https://gateway.example/openai/v1/responses"


def test_generic_responses_adapter_reads_raw_response_output() -> None:
    content = '{"image_type":"care_label","overall_confidence":90}'

    assert (
        OpenAIResponsesVisionProvider.extract_output_text(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": content},
                        ]
                    }
                ]
            }
        )
        == content
    )


def test_responses_adapter_reports_incomplete_responses_explicitly() -> None:
    from fabricassist.application.vision import VisionProviderError

    with pytest.raises(VisionProviderError, match="response limit") as error:
        OpenAIResponsesVisionProvider.reject_incomplete_response({"status": "incomplete"})

    assert error.value.code == "INCOMPLETE"


def test_generic_responses_adapter_uses_strict_boundary_schema() -> None:
    response_format = OpenAIResponsesVisionProvider.response_format()

    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    schema = response_format["schema"]
    assert isinstance(schema, dict)
    schema = cast(dict[str, object], schema)
    properties = schema["properties"]
    assert isinstance(properties, dict)
    properties = cast(dict[str, object], properties)
    required = schema["required"]
    assert isinstance(required, list)
    assert set(cast(list[str], required)) == set(properties)
    assert schema["additionalProperties"] is False

    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    definitions = cast(dict[str, object], definitions)
    material = definitions["MaterialFact"]
    assert isinstance(material, dict)
    material = cast(dict[str, object], material)
    material_properties = material["properties"]
    assert isinstance(material_properties, dict)
    material_properties = cast(dict[str, object], material_properties)
    material_required = material["required"]
    assert isinstance(material_required, list)
    assert set(cast(list[str], material_required)) == set(material_properties)
    assert material["additionalProperties"] is False


def test_care_symbol_prompt_focuses_confidence_on_decision_relevant_evidence() -> None:
    """A readable label must not be downgraded merely because its material text is absent."""
    assert PROMPT_VERSION == "care-label-extraction-v2"
    assert "confidence in the extracted care instructions" in CARE_LABEL_SYSTEM_PROMPT
    assert "square containing a circle" in CARE_LABEL_SYSTEM_PROMPT
    assert "decision-relevant field names" in CARE_LABEL_SYSTEM_PROMPT
