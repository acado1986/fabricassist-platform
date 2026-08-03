from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from fabricassist.application.garment_analysis.ports import (
    LabelExtractionRequest,
    ProviderImage,
)
from fabricassist.application.vision import VisionProviderError
from fabricassist.infrastructure.garment_analysis.providers.fake import FakeGarmentVisionProvider
from fabricassist.infrastructure.garment_analysis.providers.openai_responses import (
    OpenAIResponsesGarmentConfig,
    OpenAIResponsesGarmentVisionProvider,
)


@pytest.mark.asyncio
async def test_fake_provider_returns_versioned_unknown_label() -> None:
    result = await FakeGarmentVisionProvider().extract_labels(
        LabelExtractionRequest(images=(), attempt_number=1)
    )
    assert result.provider == "mock"
    assert result.prompt_version == "label_extraction-v1"
    assert result.value.overall_confidence == 0


@pytest.mark.asyncio
async def test_openai_rejects_unrouted_source_image() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        text = json.dumps(
            {
                "overall_confidence": 1,
                "visible_text": [
                    {
                        "image_id": "00000000-0000-0000-0000-000000000000",
                        "text": "x",
                        "language": "en",
                        "confidence": 1,
                    }
                ],
            }
        )
        return httpx.Response(
            200,
            json={
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]
            },
        )

    provider = OpenAIResponsesGarmentVisionProvider(
        OpenAIResponsesGarmentConfig(
            base_url="https://example.test/v1",
            api_key="secret",
            model="model",
            timeout_seconds=5,
            max_output_tokens=1000,
            extra_headers={},
        ),
        transport=httpx.MockTransport(responder),
    )
    request = LabelExtractionRequest(
        images=(ProviderImage(image_id=uuid4(), jpeg_bytes=b"jpeg", role="care_label"),),
        attempt_number=1,
    )
    with pytest.raises(VisionProviderError, match="invalid structured"):
        await provider.extract_labels(request)
