"""Product-information capability composition root."""

from __future__ import annotations

from fabricassist.application.product_information import ProductInformationProvider
from fabricassist.infrastructure.product_information.config import (
    HttpJsonProductInformationConfig,
)
from fabricassist.infrastructure.product_information.http_json import (
    HttpJsonProductInformationAdapter,
)
from fabricassist.infrastructure.product_information.mock import (
    MockProductInformationAdapter,
)
from fabricassist.settings import ProductInformationProviderType, Settings


def create_product_information_provider(settings: Settings) -> ProductInformationProvider:
    if settings.product_information_provider is ProductInformationProviderType.MOCK:
        return MockProductInformationAdapter()
    if settings.product_information_provider is ProductInformationProviderType.HTTP_JSON:
        return HttpJsonProductInformationAdapter(
            HttpJsonProductInformationConfig(
                base_url=settings.product_http_json_base_url,
                allowed_hosts=frozenset(
                    host.strip().lower()
                    for host in settings.product_http_json_allowed_hosts.split(",")
                    if host.strip()
                ),
                timeout_seconds=settings.product_http_json_timeout_seconds,
                max_response_bytes=settings.product_http_json_max_response_bytes,
                api_key=settings.product_http_json_api_key,
            )
        )
    raise ValueError(
        f"Unsupported product-information provider: {settings.product_information_provider}"
    )
