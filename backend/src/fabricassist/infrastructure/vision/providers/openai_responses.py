"""Isolated OpenAI Responses-compatible provider adapters."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import cast

import httpx

from fabricassist.application.conversation_provider import ConversationProviderResult
from fabricassist.application.planning import CarePlanningProviderResult
from fabricassist.application.provider import ProviderDescriptor
from fabricassist.application.provider_prompts import (
    ProviderPrompts,
)
from fabricassist.application.vision import (
    BarcodeCandidate,
    EvidenceProviderResult,
    NormalizedImage,
    VisionProviderError,
)
from fabricassist.domain.care import ProposedCarePlan
from fabricassist.domain.conversations import AssistantMessageProposal, ConversationContext
from fabricassist.domain.evidence import GarmentEvidenceDelta, GarmentEvidenceDossier
from fabricassist.infrastructure.vision.providers.common import (
    optional_int,
    validate_sources,
)

PROMPT_VERSION = "garment-evidence-v1"
SCHEMA_VERSION = "garment-evidence-v1"


@dataclass(frozen=True)
class OpenAIResponsesAdapterConfig:
    """Credentials and runtime options private to the Responses adapter."""

    base_url: str
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: int
    extra_headers: dict[str, str] = field(repr=False)
    max_output_tokens: int
    prompts: ProviderPrompts = field(default_factory=ProviderPrompts)


def _strict_schema(schema: object) -> object:
    """Make the Pydantic JSON schema valid for strict structured-output APIs."""
    if isinstance(schema, dict):
        node = cast(dict[str, object], schema)
        properties = node.get("properties")
        if isinstance(properties, dict):
            typed_properties = cast(dict[str, object], properties)
            node["required"] = list(typed_properties)
            node["additionalProperties"] = False
        for value in list(node.values()):
            _strict_schema(value)
        return node
    elif isinstance(schema, list):
        values = cast(list[object], schema)
        for value in values:
            _strict_schema(value)
        return values
    return schema


class _OpenAIResponsesVisionCapability:
    """OpenAI Responses-compatible adapter using base64 image inputs and JSON Schema."""

    def __init__(
        self,
        config: OpenAIResponsesAdapterConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._model = config.model
        self._timeout_seconds = config.timeout_seconds
        self._extra_headers = config.extra_headers
        self._max_output_tokens = config.max_output_tokens
        self._prompts = config.prompts
        self._transport = transport

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(provider="openai_responses", model=self._model)

    async def extract_evidence(
        self, images: tuple[NormalizedImage, ...], prior_dossier: object | None = None
    ) -> EvidenceProviderResult:
        _ = prior_dossier
        started = perf_counter()
        content: list[dict[str, object]] = [
            {"type": "input_text", "text": self._prompts.evidence_system}
        ]
        for image in images:
            encoded = base64.b64encode(image.jpeg_bytes).decode("ascii")
            content.append(
                {
                    "type": "input_text",
                    "text": f"Image ID: {image.image_id}; declared role: {image.role.value}.",
                }
            )
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{encoded}",
                    "detail": "high",
                }
            )
        schema = _strict_schema(GarmentEvidenceDelta.model_json_schema())
        payload: dict[str, object] = {
            "model": self._model,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": self._max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "garment_evidence_delta",
                    "strict": True,
                    "schema": schema,
                }
            },
            "store": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", **self._extra_headers}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._base_url}/responses", headers=headers, json=payload
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise VisionProviderError("PROVIDER_TIMEOUT", "Vision provider timed out") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            code = (
                "PROVIDER_RATE_LIMIT"
                if status == 429
                else "PROVIDER_UNAVAILABLE"
                if status >= 500
                else "PROVIDER_REJECTED"
            )
            raise VisionProviderError(code, f"Vision provider returned HTTP {status}") from error
        except httpx.HTTPError as error:
            raise VisionProviderError(
                "PROVIDER_NETWORK_ERROR", "Vision provider request failed"
            ) from error

        try:
            body = cast(dict[str, object], cast(object, response.json()))
            delta = GarmentEvidenceDelta.model_validate_json(_response_output_text(body))
            validate_sources(delta, images)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise VisionProviderError(
                "PROVIDER_INVALID_RESPONSE", "Vision provider returned invalid structured evidence"
            ) from error
        usage = body.get("usage")
        usage_data = cast(dict[str, object], usage) if isinstance(usage, dict) else {}
        return EvidenceProviderResult(
            delta=delta,
            provider="openai_responses",
            model=self._model,
            latency_ms=round((perf_counter() - started) * 1000),
            input_tokens=optional_int(usage_data.get("input_tokens")),
            output_tokens=optional_int(usage_data.get("output_tokens")),
        )

    async def extract_barcode_candidates(
        self, images: tuple[NormalizedImage, ...]
    ) -> tuple[BarcodeCandidate, ...]:
        # Barcode pixels are decoded locally before product lookup. This adapter
        # never turns model OCR into unverified product identifiers.
        _ = images
        return ()


def _response_output_text(response: dict[str, object]) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("Response has no output items")
    for item in cast(list[object], output):
        if not isinstance(item, dict):
            continue
        item_data = cast(dict[str, object], item)
        if item_data.get("type") != "message":
            continue
        content = item_data.get("content")
        if not isinstance(content, list):
            continue
        for part in cast(list[object], content):
            if isinstance(part, dict):
                part_data = cast(dict[str, object], part)
                if part_data.get("type") != "output_text":
                    continue
                text = part_data.get("text")
                if isinstance(text, str):
                    return text
    raise ValueError("Response has no output text")


class _OpenAIResponsesConversationCapability:
    """Responses adapter for server-owned, schema-validated follow-up answers."""

    def __init__(
        self,
        config: OpenAIResponsesAdapterConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._model = config.model
        self._timeout_seconds = config.timeout_seconds
        self._extra_headers = config.extra_headers
        self._max_output_tokens = config.max_output_tokens
        self._prompts = config.prompts
        self._transport = transport

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(provider="openai_responses", model=self._model)

    async def answer(
        self, context: ConversationContext, user_text: str
    ) -> ConversationProviderResult:
        started = perf_counter()
        prompt = (
            f"{self._prompts.conversation_system}\n\n"
            f"CONTEXT:\n{json.dumps(context.model_dump(mode='json'), sort_keys=True)}\n\n"
            f"USER QUESTION:\n{user_text}"
        )
        payload: dict[str, object] = {
            "model": self._model,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "max_output_tokens": self._max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "assistant_message_proposal",
                    "strict": True,
                    "schema": _strict_schema(AssistantMessageProposal.model_json_schema()),
                }
            },
            "store": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", **self._extra_headers}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/responses", headers=headers, json=payload
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise VisionProviderError(
                "PROVIDER_TIMEOUT", "Conversation provider timed out"
            ) from error
        except httpx.HTTPStatusError as error:
            raise VisionProviderError(
                "PROVIDER_REJECTED", "Conversation provider rejected request"
            ) from error
        except httpx.HTTPError as error:
            raise VisionProviderError(
                "PROVIDER_NETWORK_ERROR", "Conversation provider request failed"
            ) from error
        try:
            body = cast(dict[str, object], cast(object, response.json()))
            proposal = AssistantMessageProposal.model_validate_json(_response_output_text(body))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise VisionProviderError(
                "PROVIDER_INVALID_RESPONSE",
                "Conversation provider returned invalid structured output",
            ) from error
        usage = body.get("usage")
        usage_data = cast(dict[str, object], usage) if isinstance(usage, dict) else {}
        return ConversationProviderResult(
            proposal=proposal,
            provider="openai_responses",
            model=self._model,
            latency_ms=round((perf_counter() - started) * 1000),
            input_tokens=optional_int(usage_data.get("input_tokens")),
            output_tokens=optional_int(usage_data.get("output_tokens")),
        )


class _OpenAIResponsesPlanningCapability(_OpenAIResponsesConversationCapability):
    async def propose_plan(
        self,
        dossier: GarmentEvidenceDossier,
        violations: tuple[str, ...] = (),
    ) -> CarePlanningProviderResult:
        started = perf_counter()
        prompt = (
            f"{self._prompts.planning_system}\n\n"
            f"DOSSIER:\n{json.dumps(dossier.model_dump(mode='json'), sort_keys=True)}\n\n"
            f"VALIDATION VIOLATIONS:\n{json.dumps(violations)}"
        )
        payload: dict[str, object] = {
            "model": self._model,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "max_output_tokens": self._max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "proposed_care_plan",
                    "strict": True,
                    "schema": _strict_schema(ProposedCarePlan.model_json_schema()),
                }
            },
            "store": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", **self._extra_headers}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/responses", headers=headers, json=payload
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise VisionProviderError("PROVIDER_TIMEOUT", "Planning provider timed out") from error
        except httpx.HTTPStatusError as error:
            raise VisionProviderError(
                "PROVIDER_REJECTED", "Planning provider rejected request"
            ) from error
        except httpx.HTTPError as error:
            raise VisionProviderError(
                "PROVIDER_NETWORK_ERROR", "Planning provider request failed"
            ) from error
        try:
            body = cast(dict[str, object], cast(object, response.json()))
            proposal = ProposedCarePlan.model_validate_json(_response_output_text(body))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise VisionProviderError(
                "PROVIDER_INVALID_RESPONSE",
                "Planning provider returned invalid structured output",
            ) from error
        usage = body.get("usage")
        usage_data = cast(dict[str, object], usage) if isinstance(usage, dict) else {}
        return CarePlanningProviderResult(
            proposal=proposal,
            provider="openai_responses",
            model=self._model,
            latency_ms=round((perf_counter() - started) * 1000),
            input_tokens=optional_int(usage_data.get("input_tokens")),
            output_tokens=optional_int(usage_data.get("output_tokens")),
        )


class OpenAIResponsesProviderAdapter:
    """Responses HTTP adapter implementing the complete model-provider interface."""

    def __init__(
        self,
        config: OpenAIResponsesAdapterConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._vision = _OpenAIResponsesVisionCapability(config, transport=transport)
        self._planning = _OpenAIResponsesPlanningCapability(config, transport=transport)
        self._conversation = _OpenAIResponsesConversationCapability(config, transport=transport)

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._vision.descriptor

    async def extract_evidence(
        self, images: tuple[NormalizedImage, ...], prior_dossier: object | None = None
    ) -> EvidenceProviderResult:
        return await self._vision.extract_evidence(images, prior_dossier)

    async def extract_barcode_candidates(
        self, images: tuple[NormalizedImage, ...]
    ) -> tuple[BarcodeCandidate, ...]:
        return await self._vision.extract_barcode_candidates(images)

    async def answer(
        self, context: ConversationContext, user_text: str
    ) -> ConversationProviderResult:
        return await self._conversation.answer(context, user_text)

    async def propose_plan(
        self,
        dossier: GarmentEvidenceDossier,
        violations: tuple[str, ...] = (),
    ) -> CarePlanningProviderResult:
        return await self._planning.propose_plan(dossier, violations)
