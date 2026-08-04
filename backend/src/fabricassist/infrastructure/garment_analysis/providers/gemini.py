# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportAttributeAccessIssue=false, reportPrivateUsage=false, reportArgumentType=false, reportAssignmentType=false, reportOptionalIterable=false

"""Google Gemini adapter isolated behind the garment-analysis provider port."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypeVar

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from fabricassist.application.garment_analysis import (
    BarcodeEnrichmentRequest,
    GarmentInspectionRequest,
    LabelExtractionRequest,
    ModelInvocation,
    StainTreatmentRequest,
    load_prompt,
)
from fabricassist.application.vision import VisionProviderError
from fabricassist.domain.garment_analysis.models import (
    GarmentInspection,
    LabelExtraction,
    StainTreatment,
)
from fabricassist.domain.garment_analysis.parity import BarcodeEnrichment
from fabricassist.infrastructure.garment_analysis.providers.openai_responses import (
    OpenAIResponsesGarmentVisionProvider,
)

T = TypeVar("T", bound=BaseModel)
Generate = Callable[
    [str, object, types.GenerateContentConfig], Awaitable[types.GenerateContentResponse]
]


@dataclass(frozen=True)
class GeminiGarmentConfig:
    api_key: str
    model: str
    timeout_seconds: int
    max_output_tokens: int


class GeminiGarmentVisionProvider:
    def __init__(
        self, config: GeminiGarmentConfig, *, generate_content: Generate | None = None
    ) -> None:
        self._config, self._generate_override = config, generate_content

    async def inspect_garment(
        self, request: GarmentInspectionRequest
    ) -> ModelInvocation[GarmentInspection]:
        return await self._invoke("garment_inspection", request, GarmentInspection)

    async def extract_labels(
        self, request: LabelExtractionRequest
    ) -> ModelInvocation[LabelExtraction]:
        return await self._invoke("label_extraction", request, LabelExtraction)

    async def analyze_stain(
        self, request: StainTreatmentRequest
    ) -> ModelInvocation[StainTreatment]:
        return await self._invoke("stain_treatment", request, StainTreatment)

    async def extract_barcode_candidates(
        self, request: BarcodeEnrichmentRequest
    ) -> ModelInvocation[BarcodeEnrichment]:
        return await self._invoke("barcode_enrichment", request, BarcodeEnrichment)

    async def _invoke(self, branch: str, request: Any, result_type: type[T]) -> ModelInvocation[T]:
        asset, started = load_prompt(branch), perf_counter()
        parts: list[types.Part] = []
        image_ids = {x.image_id for x in request.images}
        for image in request.images:
            parts.extend(
                (
                    types.Part.from_text(
                        text=(
                            f"Image ID: {image.image_id}; role: {image.role}; "
                            f"viewpoint: {image.viewpoint}; label scope: {image.label_scope}."
                        )
                    ),
                    types.Part.from_bytes(data=image.jpeg_bytes, mime_type="image/jpeg"),
                )
            )
        config = types.GenerateContentConfig(
            system_instruction=asset.text,
            response_mime_type="application/json",
            response_json_schema=result_type.model_json_schema(),
            temperature=0,
            max_output_tokens=self._config.max_output_tokens,
        )
        try:
            if self._generate_override:
                response = await self._generate_override(self._config.model, parts, config)
            else:
                client = genai.Client(
                    api_key=self._config.api_key,
                    http_options=types.HttpOptions(timeout=self._config.timeout_seconds * 1000),
                )
                try:
                    response = await client.aio.models.generate_content(
                        model=self._config.model, contents=parts, config=config
                    )
                finally:
                    await client.aio.aclose()
                    client.close()
        except httpx.TimeoutException as e:
            raise VisionProviderError("PROVIDER_TIMEOUT", "Gemini provider timed out") from e
        except errors.APIError as e:
            status = e.code
            code = (
                "PROVIDER_RATE_LIMIT"
                if status == 429
                else "PROVIDER_AUTHENTICATION_FAILED"
                if status in {401, 403}
                else "PROVIDER_MODEL_UNAVAILABLE"
                if status == 404
                else "PROVIDER_UNAVAILABLE"
                if status >= 500
                else "PROVIDER_REJECTED"
            )
            raise VisionProviderError(code, f"Gemini provider returned HTTP {status}") from e
        except httpx.HTTPError as e:
            raise VisionProviderError(
                "PROVIDER_NETWORK_ERROR", "Gemini provider request failed"
            ) from e
        try:
            if response.text is None:
                raise ValueError("response has no text")
            value = result_type.model_validate_json(response.text)
            OpenAIResponsesGarmentVisionProvider._validate_sources(value, image_ids)
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            raise VisionProviderError(
                "PROVIDER_INVALID_RESPONSE", "Gemini provider returned invalid structured output"
            ) from e
        usage = response.usage_metadata

        def get_usage(name: str) -> int | None:
            value = getattr(usage, name, None) if usage is not None else None
            return value if isinstance(value, int) else None

        return ModelInvocation(
            value=value,
            provider="gemini",
            model=self._config.model,
            prompt_version=asset.version,
            prompt_checksum=asset.checksum,
            schema_version=value.schema_version,
            latency_ms=round((perf_counter() - started) * 1000),
            attempt_number=request.attempt_number,
            input_tokens=get_usage("prompt_token_count"),
            output_tokens=get_usage("candidates_token_count"),
            total_tokens=get_usage("total_token_count"),
            cached_tokens=get_usage("cached_content_token_count"),
            thought_tokens=get_usage("thoughts_token_count"),
            tool_tokens=get_usage("tool_use_prompt_token_count"),
            response_model_version=getattr(response, "model_version", None),
            response_id=getattr(response, "response_id", None),
        )
