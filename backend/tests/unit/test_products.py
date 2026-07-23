# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

import pytest

from fabricassist.application.products import (
    HttpProductInformationProvider,
    MockProductInformationProvider,
)
from fabricassist.domain.products import ProductLookupError, ProductMatchStatus, normalize_barcode


def test_normalizes_and_validates_supported_barcodes() -> None:
    assert normalize_barcode("4006 3813 3393 1") == "4006381333931"
    assert normalize_barcode("036000291452") == "036000291452"


@pytest.mark.parametrize("barcode", ["4006381333932", "123", "not-a-barcode"])
def test_rejects_bad_barcode(barcode: str) -> None:
    with pytest.raises(ValueError):
        normalize_barcode(barcode)


@pytest.mark.asyncio
async def test_mock_lookup_is_no_network_and_returns_known_statuses() -> None:
    provider = MockProductInformationProvider()
    assert (await provider.lookup("4006381333931")).status is ProductMatchStatus.EXACT
    assert (await provider.lookup("036000291452")).status is ProductMatchStatus.MULTIPLE_CANDIDATES
    assert (await provider.lookup("4006381333931")).product is not None


@pytest.mark.asyncio
async def test_http_catalog_rejects_private_dns_answers_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = HttpProductInformationProvider(
        "https://catalog.example/products", "catalog.example", "", 10, 1024
    )
    monkeypatch.setattr(
        "fabricassist.application.products.socket.getaddrinfo",
        lambda *_args: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    with pytest.raises(ProductLookupError, match="PRODUCT_URL_PRIVATE_ADDRESS"):
        await provider.lookup("4006381333931")
