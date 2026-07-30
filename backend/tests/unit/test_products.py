# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

import httpx
import pytest

from fabricassist.application.product_information import (
    PermanentProductInformationError,
    RetryableProductInformationError,
)
from fabricassist.domain.products import ProductMatchStatus, normalize_barcode
from fabricassist.infrastructure.product_information.config import (
    HttpJsonProductInformationConfig,
)
from fabricassist.infrastructure.product_information.http_json import (
    HttpJsonProductInformationAdapter,
)
from fabricassist.infrastructure.product_information.mock import (
    MockProductInformationAdapter,
)


def test_normalizes_and_validates_supported_barcodes() -> None:
    assert normalize_barcode("4006 3813 3393 1") == "4006381333931"
    assert normalize_barcode("036000291452") == "036000291452"


@pytest.mark.parametrize("barcode", ["4006381333932", "123", "not-a-barcode"])
def test_rejects_bad_barcode(barcode: str) -> None:
    with pytest.raises(ValueError):
        normalize_barcode(barcode)


@pytest.mark.asyncio
async def test_mock_lookup_is_no_network_and_returns_known_statuses() -> None:
    provider = MockProductInformationAdapter()
    assert (await provider.lookup("4006381333931")).status is ProductMatchStatus.EXACT
    assert (await provider.lookup("036000291452")).status is ProductMatchStatus.MULTIPLE_CANDIDATES
    assert (await provider.lookup("4006381333931")).product is not None


@pytest.mark.asyncio
async def test_http_catalog_rejects_private_dns_answers_before_request() -> None:
    provider = HttpJsonProductInformationAdapter(
        HttpJsonProductInformationConfig(
            base_url="https://catalog.example/products",
            allowed_hosts=frozenset({"catalog.example"}),
            timeout_seconds=10,
            max_response_bytes=1024,
        ),
        resolver=lambda *_args: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    with pytest.raises(
        PermanentProductInformationError,
        match="PRODUCT_URL_PRIVATE_ADDRESS",
    ):
        await provider.lookup("4006381333931")


def public_dns(
    *_args: object,
) -> list[tuple[None, None, None, None, tuple[str, int]]]:
    return [(None, None, None, None, ("93.184.216.34", 443))]


@pytest.mark.asyncio
async def test_http_catalog_preserves_validated_source_and_license_provenance() -> None:
    async def response(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://catalog.example/products/4006381333931"
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "status": "exact",
                "source_name": "Synthetic catalog",
                "source_reference": "catalog:4006381333931",
                "license_name": "synthetic-test-data",
                "product": {
                    "brand": "Fixture",
                    "name": "Shirt",
                    "variant": "blue",
                    "materials": ["cotton"],
                },
            },
        )

    provider = HttpJsonProductInformationAdapter(
        HttpJsonProductInformationConfig(
            base_url="https://catalog.example/products",
            allowed_hosts=frozenset({"catalog.example"}),
            timeout_seconds=10,
            max_response_bytes=4096,
        ),
        transport=httpx.MockTransport(response),
        resolver=public_dns,
    )

    result = await provider.lookup("4006381333931")

    assert result.status is ProductMatchStatus.EXACT
    assert result.provider == "http_json"
    assert result.source_name == "Synthetic catalog"
    assert result.source_reference == "catalog:4006381333931"
    assert result.license_name == "synthetic-test-data"
    assert result.product == {
        "brand": "Fixture",
        "name": "Shirt",
        "variant": "blue",
        "materials": ["cotton"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "headers", "body", "error_type", "error_code"),
    [
        (
            302,
            {"location": "https://other.example/product"},
            b"",
            PermanentProductInformationError,
            "PRODUCT_REDIRECT_REJECTED",
        ),
        (
            200,
            {"content-type": "text/html"},
            b"not json",
            PermanentProductInformationError,
            "PRODUCT_RESPONSE_REJECTED",
        ),
        (
            503,
            {"content-type": "application/json"},
            b"{}",
            RetryableProductInformationError,
            "PRODUCT_PROVIDER_UNAVAILABLE",
        ),
    ],
)
async def test_http_catalog_translates_transport_and_content_failures(
    status: int,
    headers: dict[str, str],
    body: bytes,
    error_type: type[Exception],
    error_code: str,
) -> None:
    provider = HttpJsonProductInformationAdapter(
        HttpJsonProductInformationConfig(
            base_url="https://catalog.example/products",
            allowed_hosts=frozenset({"catalog.example"}),
            timeout_seconds=10,
            max_response_bytes=16,
        ),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status, headers=headers, content=body)
        ),
        resolver=public_dns,
    )
    with pytest.raises(error_type, match=error_code):
        await provider.lookup("4006381333931")
