"""Allow-listed HTTPS JSON product catalog adapter."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from fabricassist.application.product_information import (
    CatalogProduct,
    PermanentProductInformationError,
    ProductLookupResult,
    RetryableProductInformationError,
)
from fabricassist.domain.products import ProductMatchStatus
from fabricassist.infrastructure.product_information.config import (
    HttpJsonProductInformationConfig,
)


class HttpCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: ProductMatchStatus = ProductMatchStatus.NOT_FOUND
    source_name: Annotated[str, StringConstraints(max_length=255)] | None = None
    source_reference: Annotated[str, StringConstraints(max_length=2_048)] | None = None
    license_name: Annotated[str, StringConstraints(max_length=255)] | None = None
    product: CatalogProduct | None = None


class HttpJsonProductInformationAdapter:
    def __init__(
        self,
        config: HttpJsonProductInformationConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Callable[
            [str, int | None],
            Sequence[tuple[object, object, object, object, tuple[str, int]]],
        ]
        | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._resolver = resolver or socket.getaddrinfo

    async def lookup(self, barcode: str) -> ProductLookupResult:
        url = f"{self._config.base_url.rstrip('/')}/{barcode}"
        parsed = httpx.URL(url)
        if (
            parsed.scheme != "https"
            or not parsed.host
            or parsed.host.lower() not in self._config.allowed_hosts
        ):
            raise PermanentProductInformationError("PRODUCT_URL_NOT_ALLOWED")
        for info in self._resolver(parsed.host, None):
            address = ipaddress.ip_address(info[4][0])
            if not address.is_global:
                raise PermanentProductInformationError("PRODUCT_URL_PRIVATE_ADDRESS")
        headers = (
            {"Authorization": f"Bearer {self._config.api_key}"} if self._config.api_key else {}
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._config.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 404:
                        return ProductLookupResult(ProductMatchStatus.NOT_FOUND, "http_json")
                    if 300 <= response.status_code < 400:
                        raise PermanentProductInformationError("PRODUCT_REDIRECT_REJECTED")
                    if response.status_code == 429 or response.status_code >= 500:
                        raise RetryableProductInformationError("PRODUCT_PROVIDER_UNAVAILABLE")
                    if response.status_code >= 400:
                        raise PermanentProductInformationError("PRODUCT_PROVIDER_REJECTED")
                    if "application/json" not in response.headers.get("content-type", ""):
                        raise PermanentProductInformationError("PRODUCT_RESPONSE_REJECTED")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self._config.max_response_bytes:
                            raise PermanentProductInformationError("PRODUCT_RESPONSE_TOO_LARGE")
                        chunks.append(chunk)
        except httpx.TimeoutException as error:
            raise RetryableProductInformationError("PRODUCT_PROVIDER_TIMEOUT") from error
        except httpx.HTTPError as error:
            raise RetryableProductInformationError("PRODUCT_PROVIDER_UNAVAILABLE") from error
        try:
            data = HttpCatalogResponse.model_validate_json(b"".join(chunks))
        except ValidationError as error:
            raise PermanentProductInformationError("PRODUCT_RESPONSE_REJECTED") from error
        return ProductLookupResult(
            data.status,
            "http_json",
            data.source_name or "Catalog",
            data.source_reference,
            data.license_name,
            data.product.model_dump(mode="json") if data.product else None,
        )
