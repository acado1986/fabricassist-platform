from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from fabricassist.application.vision import NormalizedImage, VisionProviderError
from fabricassist.domain.conversations import ConversationContext
from fabricassist.domain.evidence import GarmentEvidenceDossier, ImageRole
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
        debug_logging=True,
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
async def test_responses_provider_debug_logging_uses_safe_summaries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def responder(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"observations":[],"care_facts":[],"uncertainties":[]}',
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            },
        )

    provider = OpenAIResponsesProviderAdapter(_config(), transport=httpx.MockTransport(responder))
    with caplog.at_level("DEBUG"):
        await provider.extract_evidence(
            (
                NormalizedImage(
                    uuid4(),
                    b"private-image-bytes",
                    "0" * 64,
                    640,
                    640,
                    ImageRole.CARE_LABEL,
                ),
            )
        )

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "OpenAI Responses request summary" in messages
    assert "OpenAI Responses response summary" in messages
    assert "private-image-bytes" not in messages
    request_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "OpenAI Responses request summary"
    )
    assert request_record.request_summary["image_count"] == 1


@pytest.mark.asyncio
async def test_responses_provider_categorizes_provider_rejection() -> None:
    provider = OpenAIResponsesProviderAdapter(
        _config(),
        transport=httpx.MockTransport(lambda _: httpx.Response(400, json={"error": {}})),
    )

    with pytest.raises(VisionProviderError, match="HTTP 400") as error:
        await provider.extract_evidence(())

    assert error.value.code == "PROVIDER_REJECTED"


@pytest.mark.asyncio
async def test_responses_provider_satisfies_planning_and_conversation_contracts() -> None:
    requested_schemas: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        schema_name = payload["text"]["format"]["name"]
        requested_schemas.append(schema_name)
        if schema_name == "proposed_care_plan":
            output = {
                "classification": "provisional",
                "cleaning": {
                    "method": "unknown",
                    "maximum_temperature_c": None,
                },
                "uncertainties": ["care_label_facts_unknown"],
                "follow_up_questions": ["Please add a clear care-label photo."],
            }
        else:
            output = {
                "text": "Please add a clear care-label photo.",
                "actionable_claims": [],
                "evidence_ids": [],
                "uncertainties": ["care_label_missing"],
                "follow_up_questions": ["Can you add the care label?"],
            }
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(output)}],
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 10},
            },
        )

    provider = OpenAIResponsesProviderAdapter(_config(), transport=httpx.MockTransport(responder))
    planning = await provider.propose_plan(GarmentEvidenceDossier())
    conversation = await provider.answer(
        ConversationContext(
            garment_id=uuid4(),
            analysis_revision_id=uuid4(),
            dossier={},
            validated_plan={},
            validation={},
        ),
        "Can I wash this?",
    )

    assert planning.provider == "openai_responses"
    assert planning.proposal.cleaning.method == "unknown"
    assert conversation.provider == "openai_responses"
    assert conversation.proposal.actionable_claims == []
    assert requested_schemas == [
        "proposed_care_plan",
        "assistant_message_proposal",
    ]
