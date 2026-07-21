"""Deterministic local and OpenAI-compatible structured vision adapters."""

from __future__ import annotations

import base64
import json
import logging
import time
from collections.abc import Callable
from typing import cast
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from fabricassist.application.vision import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    LabelExtractionPayload,
    NormalizedImage,
    ProviderResult,
    VisionExtractionProvider,
    VisionProviderError,
)
from fabricassist.settings import Settings

_SYSTEM_PROMPT = """Extract care evidence from the separately identified care-label image and,
when supplied, the garment image.
The care label is authoritative for every care process. Use the garment image only for visible
garment context and never infer permission to wash, bleach, dry, iron, or dry-clean from appearance.
When both supplied images are usable, image_type must be both; for a label-only request it must be
care_label; for a garment-only request it must be garment. Return JSON only with keys:
image_type, original_visible_text, materials, wash_permission, max_wash_temperature_c,
wash_process, bleach_permission, tumble_permission, iron_permission, dry_clean_permission,
written_warnings, overall_confidence, uncertain_fields.
Preserve visible text exactly. Use unknown when absent; never infer a missing symbol."""

logger = logging.getLogger("fabricassist.vision")


def _debug_request(
    settings: Settings,
    *,
    provider: str,
    model: str,
    images: tuple[NormalizedImage, ...],
    output_tokens: int,
) -> None:
    """Emit opt-in diagnostics without image bytes, headers, keys, or endpoint URLs."""
    if not settings.vision_debug_logging:
        return
    logger.warning(
        "vision_model_request %s",
        json.dumps(
            {
                "provider": provider,
                "model": model,
                "system_prompt": _SYSTEM_PROMPT,
                "images": [
                    {
                        "kind": image.kind,
                        "normalized_sha256": image.sha256,
                        "width": image.width,
                        "height": image.height,
                        "jpeg_bytes": len(image.jpeg_bytes),
                    }
                    for image in images
                ],
                "max_input_tokens": settings.vision_max_input_tokens,
                "max_output_tokens": output_tokens,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


def _debug_response(
    settings: Settings,
    *,
    provider: str,
    model: str,
    output_text: str | None,
    status: str | None = None,
) -> None:
    """Emit the model's text answer only for explicit local debug sessions."""
    if not settings.vision_debug_logging:
        return
    logger.warning(
        "vision_model_response %s",
        json.dumps(
            {
                "provider": provider,
                "model": model,
                "status": status,
                "model_output": output_text,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


class MockVisionProvider:
    """No-network local provider that deliberately produces a review-safe output."""

    async def extract_label(self, images: tuple[NormalizedImage, ...]) -> ProviderResult:
        _ = images
        return ProviderResult(
            payload=LabelExtractionPayload(
                image_type="care_label",
                overall_confidence=0,
                uncertain_fields=["mock_provider_has_no_label_recognition"],
            ),
            provider="mock",
            model="deterministic-review-safe",
            latency_ms=0,
        )


class OpenAICompatibleVisionProvider:
    """Uses the standard OpenAI-compatible chat-completions protocol with strict JSON parsing."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.vision_base_url.rstrip("/")
        self._api_key = settings.vision_api_key
        self._model = settings.vision_model
        self._timeout = settings.vision_timeout_seconds
        self._max_output_tokens = settings.vision_max_output_tokens

    async def extract_label(self, images: tuple[NormalizedImage, ...]) -> ProviderResult:
        _debug_request(
            self._settings,
            provider="openai_compatible",
            model=self._model,
            images=images,
            output_tokens=self._max_output_tokens,
        )
        request_content: list[dict[str, object]] = [
            {"type": "text", "text": "Analyse both supplied images together."}
        ]
        for image in images:
            encoded = base64.b64encode(image.jpeg_bytes).decode("ascii")
            request_content.extend(
                [
                    {"type": "text", "text": f"The next image is the {image.kind}."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ]
            )
        request = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": self._max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": request_content},
            ],
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=request,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise VisionProviderError("TRANSIENT", "Vision provider timed out.") from error
        except httpx.HTTPStatusError as error:
            code = "TRANSIENT" if error.response.status_code >= 500 else "PERMANENT"
            raise VisionProviderError(code, "Vision provider rejected the request.") from error
        except httpx.HTTPError as error:
            raise VisionProviderError("TRANSIENT", "Vision provider connection failed.") from error
        try:
            body = response.json()
            output_text = body["choices"][0]["message"]["content"]
            _debug_response(
                self._settings,
                provider="openai_compatible",
                model=self._model,
                output_text=output_text if isinstance(output_text, str) else None,
            )
            payload = LabelExtractionPayload.model_validate(json.loads(output_text))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
            raise VisionProviderError(
                "SCHEMA", "Vision provider returned invalid structured data."
            ) from error
        usage = body.get("usage", {})
        return ProviderResult(
            payload=payload,
            provider="openai_compatible",
            model=self._model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )


class OpenAIResponsesVisionProvider:
    """Generic OpenAI Responses API adapter with configurable gateway headers.

    It supports self-hosted gateways and API-management proxies without naming
    any vendor in application or domain code.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.vision_base_url.rstrip("/")
        self._api_key = settings.vision_api_key
        self._model = settings.vision_model
        self._timeout = settings.vision_timeout_seconds
        self._max_output_tokens = settings.vision_max_output_tokens
        self._extra_headers = cast(dict[str, str], json.loads(settings.vision_extra_headers_json))

    def endpoint_url(self) -> str:
        return f"{self._base_url}/responses"

    @classmethod
    def response_format(cls) -> dict[str, object]:
        """Build a strict provider schema from the validated boundary model."""
        schema = cls._make_schema_strict(LabelExtractionPayload.model_json_schema())
        return {
            "type": "json_schema",
            "name": "fabricassist_label_extraction",
            "strict": True,
            "schema": schema,
        }

    @classmethod
    def _make_schema_strict(cls, value: object) -> object:
        """Adapt Pydantic JSON Schema to the strict Responses API subset."""
        if isinstance(value, list):
            return [cls._make_schema_strict(item) for item in cast(list[object], value)]
        if not isinstance(value, dict):
            return value

        source = cast(dict[str, object], value)
        result = {
            key: cls._make_schema_strict(item) for key, item in source.items() if key != "default"
        }
        properties = result.get("properties")
        if result.get("type") == "object" and isinstance(properties, dict):
            typed_properties = cast(dict[str, object], properties)
            result["required"] = list(typed_properties)
            result["additionalProperties"] = False
        return result

    @staticmethod
    def extract_output_text(body: object) -> str:
        """Read both convenience and raw Responses API text representations."""
        if not isinstance(body, dict):
            raise ValueError("Response body is not an object.")
        typed_body = cast(dict[str, object], body)
        direct = typed_body.get("output_text")
        if isinstance(direct, str) and direct:
            return direct
        output = typed_body.get("output")
        if not isinstance(output, list):
            raise ValueError("Response has no output text.")
        fragments: list[str] = []
        for raw_item in cast(list[object], output):
            if not isinstance(raw_item, dict):
                continue
            item = cast(dict[str, object], raw_item)
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for raw_part in cast(list[object], content):
                if isinstance(raw_part, dict):
                    part = cast(dict[str, object], raw_part)
                    if part.get("type") != "output_text":
                        continue
                    text = part.get("text")
                    if isinstance(text, str):
                        fragments.append(text)
        if not fragments:
            raise ValueError("Response has no output text.")
        return "".join(fragments)

    @staticmethod
    def reject_incomplete_response(body: object) -> None:
        """Surface a Responses token-limit result separately from malformed output."""
        if not isinstance(body, dict):
            return
        typed_body = cast(dict[str, object], body)
        if typed_body.get("status") == "incomplete":
            raise VisionProviderError("INCOMPLETE", "Vision provider reached its response limit.")

    async def extract_label(self, images: tuple[NormalizedImage, ...]) -> ProviderResult:
        _debug_request(
            self._settings,
            provider="openai_responses",
            model=self._model,
            images=images,
            output_tokens=self._max_output_tokens,
        )
        request_content: list[dict[str, object]] = [
            {"type": "input_text", "text": "Analyse both supplied images together."}
        ]
        for image in images:
            encoded = base64.b64encode(image.jpeg_bytes).decode("ascii")
            request_content.extend(
                [
                    {"type": "input_text", "text": f"The next image is the {image.kind}."},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded}"},
                ]
            )
        request = {
            "model": self._model,
            "temperature": 0,
            "max_output_tokens": self._max_output_tokens,
            "text": {"format": self.response_format()},
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": _SYSTEM_PROMPT}]},
                {"role": "user", "content": request_content},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}", **self._extra_headers}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self.endpoint_url(), json=request, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise VisionProviderError("TRANSIENT", "Vision provider timed out.") from error
        except httpx.HTTPStatusError as error:
            code = "TRANSIENT" if error.response.status_code >= 500 else "PERMANENT"
            raise VisionProviderError(code, "Vision provider rejected the request.") from error
        except httpx.HTTPError as error:
            raise VisionProviderError("TRANSIENT", "Vision provider connection failed.") from error
        try:
            raw_body = response.json()
            if not isinstance(raw_body, dict):
                raise ValueError("Response body is not an object.")
            body = cast(dict[str, object], raw_body)
            status = body.get("status")
            self.reject_incomplete_response(body)
            output_text = self.extract_output_text(body)
            _debug_response(
                self._settings,
                provider="openai_responses",
                model=self._model,
                output_text=output_text,
                status=status if isinstance(status, str) else None,
            )
            payload = LabelExtractionPayload.model_validate(json.loads(output_text))
        except (TypeError, ValueError, json.JSONDecodeError, ValidationError) as error:
            raise VisionProviderError(
                "SCHEMA", "Vision provider returned invalid structured data."
            ) from error
        usage_raw = body.get("usage")
        usage = cast(dict[str, object], usage_raw) if isinstance(usage_raw, dict) else {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return ProviderResult(
            payload=payload,
            provider="openai_responses",
            model=self._model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
        )


class AzureOpenAIVisionProvider:
    """Azure deployment-based chat-completions adapter using the Azure API-key header."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._endpoint = settings.azure_openai_endpoint.rstrip("/")
        self._api_key = settings.azure_openai_api_key
        self._deployment = settings.azure_openai_deployment
        self._api_version = settings.azure_openai_api_version
        self._timeout = settings.vision_timeout_seconds
        self._max_output_tokens = settings.vision_max_output_tokens

    def endpoint_url(self) -> str:
        deployment = quote(self._deployment, safe="")
        return (
            f"{self._endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )

    async def extract_label(self, images: tuple[NormalizedImage, ...]) -> ProviderResult:
        _debug_request(
            self._settings,
            provider="azure_openai",
            model=self._deployment,
            images=images,
            output_tokens=self._max_output_tokens,
        )
        request_content: list[dict[str, object]] = [
            {"type": "text", "text": "Analyse both supplied images together."}
        ]
        for image in images:
            encoded = base64.b64encode(image.jpeg_bytes).decode("ascii")
            request_content.extend(
                [
                    {"type": "text", "text": f"The next image is the {image.kind}."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ]
            )
        request = {
            "temperature": 0,
            "max_tokens": self._max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": request_content},
            ],
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self.endpoint_url(),
                    json=request,
                    headers={"api-key": self._api_key},
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise VisionProviderError("TRANSIENT", "Azure OpenAI timed out.") from error
        except httpx.HTTPStatusError as error:
            code = "TRANSIENT" if error.response.status_code >= 500 else "PERMANENT"
            raise VisionProviderError(code, "Azure OpenAI rejected the request.") from error
        except httpx.HTTPError as error:
            raise VisionProviderError("TRANSIENT", "Azure OpenAI connection failed.") from error
        try:
            body = response.json()
            output_text = body["choices"][0]["message"]["content"]
            _debug_response(
                self._settings,
                provider="azure_openai",
                model=self._deployment,
                output_text=output_text if isinstance(output_text, str) else None,
            )
            payload = LabelExtractionPayload.model_validate(json.loads(output_text))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
            raise VisionProviderError(
                "SCHEMA", "Azure OpenAI returned invalid structured data."
            ) from error
        usage = body.get("usage", {})
        return ProviderResult(
            payload=payload,
            provider="azure_openai",
            model=self._deployment,
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )


def get_vision_provider(settings: Settings) -> VisionExtractionProvider:
    """Resolve the configured adapter at the infrastructure boundary only."""
    return DEFAULT_PROVIDER_REGISTRY.resolve(settings)


ProviderFactory = Callable[[Settings], VisionExtractionProvider]


class ProviderRegistry:
    """Maps stable provider identifiers to infrastructure adapter factories.

    Application orchestration consumes only VisionExtractionProvider. Adding a
    vendor requires registering an adapter here, not changing worker, API,
    schemas, or deterministic care rules.
    """

    def __init__(self, factories: dict[str, ProviderFactory]) -> None:
        self._factories = dict(factories)

    def resolve(self, settings: Settings) -> VisionExtractionProvider:
        try:
            factory = self._factories[settings.vision_provider]
        except KeyError as error:
            raise ValueError(f"Unsupported vision provider: {settings.vision_provider}") from error
        return factory(settings)


DEFAULT_PROVIDER_REGISTRY = ProviderRegistry(
    {
        "mock": lambda _settings: MockVisionProvider(),
        "openai_compatible": OpenAICompatibleVisionProvider,
        "openai_responses": OpenAIResponsesVisionProvider,
        "azure_openai": AzureOpenAIVisionProvider,
    }
)


__all__ = ["PROMPT_VERSION", "SCHEMA_VERSION", "get_vision_provider"]
