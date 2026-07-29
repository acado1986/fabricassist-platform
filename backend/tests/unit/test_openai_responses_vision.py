from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from fabricassist.application.vision import NormalizedImage, VisionProviderError
from fabricassist.domain.evidence import ImageRole
from fabricassist.infrastructure.vision.providers import (
    OpenAIResponsesAdapterConfig,
    OpenAIResponsesProviderAdapter,
)


def _config() -> OpenAIResponsesAdapterConfig:
    return OpenAIResponsesAdapterConfig(
        base_url="https://provider.example/v1",
        api_key="test-key",
        model="test-vision-model",
        timeout_seconds=120,
        extra_headers={"X-Gateway-Key": "gateway-secret"},
        max_output_tokens=16_000,
    )


@pytest.mark.asyncio
async def test_responses_provider_sends_images_and_validates_structured_evidence() -> None:
    image_id = uuid4()
    observed_request: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        observed_request.update(json.loads(request.content))
        assert request.url == "https://provider.example/v1/responses"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["x-gateway-key"] == "gateway-secret"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
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
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 123, "output_tokens": 45},
            },
        )

    provider = OpenAIResponsesProviderAdapter(_config(), transport=httpx.MockTransport(responder))
    result = await provider.extract_evidence(
        (
            NormalizedImage(
                image_id,
                b"jpeg-bytes",
                "0" * 64,
                640,
                640,
                ImageRole.CARE_LABEL,
            ),
        )
    )

    assert result.provider == "openai_responses"
    assert result.model == "test-vision-model"
    assert result.input_tokens == 123
    assert result.output_tokens == 45
    assert result.delta.care_facts[0].code == "machine_wash"
    content = observed_request["input"][0]["content"]  # type: ignore[index]
    assert content[2]["image_url"].startswith("data:image/jpeg;base64,")  # type: ignore[index]
    response_format = observed_request["text"]["format"]  # type: ignore[index]
    assert response_format["strict"] is True  # type: ignore[index]
    assert response_format["schema"]["additionalProperties"] is False  # type: ignore[index]


@pytest.mark.asyncio
async def test_responses_provider_categorizes_provider_rejection() -> None:
    provider = OpenAIResponsesProviderAdapter(
        _config(),
        transport=httpx.MockTransport(lambda _: httpx.Response(400, json={"error": {}})),
    )

    with pytest.raises(VisionProviderError, match="HTTP 400") as error:
        await provider.extract_evidence(())

    assert error.value.code == "PROVIDER_REJECTED"
