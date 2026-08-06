"""Deterministic v2 image normalization shared by upload and worker paths."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps

NORMALIZATION_VERSION = "normalized-jpeg-v2"


@dataclass(frozen=True)
class NormalizedImageMetadata:
    jpeg_bytes: bytes
    sha256: str
    width: int
    height: int


def normalize_image_bytes(raw: bytes) -> NormalizedImageMetadata:
    """Strip metadata and orientation differences before exact-cache hashing."""
    try:
        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((2048, 2048))
            output = BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
    except (OSError, ValueError) as error:
        raise ValueError("IMAGE_INVALID") from error
    jpeg_bytes = output.getvalue()
    return NormalizedImageMetadata(
        jpeg_bytes=jpeg_bytes,
        sha256=hashlib.sha256(jpeg_bytes).hexdigest(),
        width=image.width,
        height=image.height,
    )
