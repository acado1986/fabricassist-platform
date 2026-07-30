# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

from uuid import uuid4

import pytest
import zxingcpp
from PIL import Image

from fabricassist.application.vision import NormalizedImage, decode_barcodes
from fabricassist.domain.evidence import ImageRole
from fabricassist.infrastructure.vision.providers.mock import MockModelCapabilityAdapter


@pytest.mark.asyncio
async def test_mock_evidence_is_source_referenced() -> None:
    result = await MockModelCapabilityAdapter().extract_evidence(
        (NormalizedImage(uuid4(), b"x", "0" * 64, 320, 320, ImageRole.CARE_LABEL),)
    )
    assert result.delta.observations[0].source.role is ImageRole.CARE_LABEL


@pytest.mark.asyncio
async def test_mock_vision_does_not_fabricate_barcode_digits() -> None:
    candidates = await MockModelCapabilityAdapter().extract_barcode_candidates(
        (NormalizedImage(uuid4(), b"x", "0" * 64, 320, 320, ImageRole.BARCODE_BRAND_LABEL),)
    )
    assert candidates == ()


def test_decodes_qr_pixels_without_an_ocr_or_network_provider() -> None:
    image = zxingcpp.write_barcode_to_image(
        zxingcpp.create_barcode("4006381333931", zxingcpp.BarcodeFormat.QRCode), 4
    )
    rendered = Image.frombuffer("L", (image.shape[1], image.shape[0]), image, "raw", "L", 0, 1)
    from io import BytesIO

    data = BytesIO()
    rendered.save(data, "PNG")
    candidates = decode_barcodes(
        (
            NormalizedImage(
                uuid4(), data.getvalue(), "0" * 64, 320, 320, ImageRole.BARCODE_BRAND_LABEL
            ),
        )
    )
    assert [candidate.value for candidate in candidates] == ["4006381333931"]
