"""Deterministic no-network product-information adapter."""

from __future__ import annotations

from fabricassist.application.product_information import ProductLookupResult
from fabricassist.domain.products import ProductMatchStatus


class MockProductInformationAdapter:
    async def lookup(self, barcode: str) -> ProductLookupResult:
        if barcode == "4006381333931":
            return ProductLookupResult(
                ProductMatchStatus.EXACT,
                "mock",
                "Mock catalog",
                "mock:4006381333931",
                "test-data",
                {
                    "brand": "FabricAssist fixture",
                    "name": "Cotton shirt",
                    "variant": "blue",
                    "materials": ["cotton"],
                },
            )
        if barcode == "036000291452":
            return ProductLookupResult(
                ProductMatchStatus.MULTIPLE_CANDIDATES,
                "mock",
                "Mock catalog",
                "mock:036000291452",
                "test-data",
            )
        return ProductLookupResult(
            ProductMatchStatus.NOT_FOUND,
            "mock",
            "Mock catalog",
            f"mock:{barcode}",
            "test-data",
        )
