# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportAttributeAccessIssue=false, reportPrivateUsage=false, reportArgumentType=false, reportAssignmentType=false, reportOptionalIterable=false

"""OpenAI Responses-compatible garment-analysis adapter."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from fabricassist.application.garment_analysis import (
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

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class OpenAIResponsesGarmentConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    max_output_tokens: int
    extra_headers: dict[str, str]


class OpenAIResponsesGarmentVisionProvider:
    def __init__(
        self,
        config: OpenAIResponsesGarmentConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config, self._transport = config, transport

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

    async def _invoke(self, branch: str, request: Any, result_type: type[T]) -> ModelInvocation[T]:
        asset, started = load_prompt(branch), perf_counter()
        content: list[dict[str, object]] = [{"type": "input_text", "text": asset.text}]
        image_ids = {image.image_id for image in request.images}
        for image in request.images:
            content += [
                {
                    "type": "input_text",
                    "text": (
                        f"Image ID: {image.image_id}; role: {image.role}; "
                        f"viewpoint: {image.viewpoint}; label scope: {image.label_scope}."
                    ),
                },
                {
                    "type": "input_image",
                    "image_url": "data:image/jpeg;base64,"
                    + base64.b64encode(image.jpeg_bytes).decode("ascii"),
                    "detail": "high",
                },
            ]
        schema = result_type.model_json_schema()
        payload: dict[str, object] = {
            "model": self._config.model,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": self._config.max_output_tokens,
            "text": {
                "format": {"type": "json_schema", "name": branch, "strict": True, "schema": schema}
            },
            "store": False,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._config.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    self._config.base_url.rstrip("/") + "/responses",
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                        **self._config.extra_headers,
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as e:
            raise VisionProviderError("PROVIDER_TIMEOUT", "Garment provider timed out") from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
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
            raise VisionProviderError(code, f"Garment provider returned HTTP {status}") from e
        except httpx.HTTPError as e:
            raise VisionProviderError(
                "PROVIDER_NETWORK_ERROR", "Garment provider request failed"
            ) from e
        try:
            body = response.json()
            text = next(
                part["text"]
                for item in body["output"]
                if item.get("type") == "message"
                for part in item["content"]
                if part.get("type") == "output_text"
            )
            value = result_type.model_validate_json(text)
            self._validate_sources(value, image_ids)
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as e:
            raise VisionProviderError(
                "PROVIDER_INVALID_RESPONSE", "Garment provider returned invalid structured output"
            ) from e
        usage = body.get("usage") if isinstance(body, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        return ModelInvocation(
            value=value,
            provider="openai_responses",
            model=self._config.model,
            prompt_version=asset.version,
            prompt_checksum=asset.checksum,
            schema_version=value.schema_version,
            latency_ms=round((perf_counter() - started) * 1000),
            attempt_number=request.attempt_number,
            input_tokens=self._int(usage.get("input_tokens")),
            output_tokens=self._int(usage.get("output_tokens")),
            total_tokens=self._int(usage.get("total_tokens")),
            response_id=body.get("id") if isinstance(body.get("id"), str) else None,
            response_model_version=body.get("model")
            if isinstance(body.get("model"), str)
            else None,
        )

    @staticmethod
    def _int(value: object) -> int | None:
        return value if isinstance(value, int) and value >= 0 else None

    @staticmethod
    def _validate_sources(value: BaseModel, image_ids: set[object]) -> None:
        data = value.model_dump(mode="python")

        def walk(item: object, key: str = "") -> None:
            if isinstance(item, dict):
                for child_key, child in item.items():
                    if (
                        child_key in {"image_id", "source_image_id"}
                        and child is not None
                        and child not in image_ids
                    ):
                        raise ValueError("response references an unrouted image")
                    if child_key == "source_image_ids" and any(
                        source not in image_ids for source in child
                    ):
                        raise ValueError("response references an unrouted image")
                    walk(child, child_key)
            elif isinstance(item, list | tuple):
                for child in item:
                    walk(child, key)

        walk(data)
