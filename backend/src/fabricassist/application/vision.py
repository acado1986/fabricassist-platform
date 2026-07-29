"""Application port for source-referenced evidence extraction."""
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol
from uuid import UUID

import zxingcpp
from PIL import Image

from fabricassist.application.provider import ProviderDescriptor
from fabricassist.domain.evidence import GarmentEvidenceDelta, ImageRole

EVIDENCE_PROMPT_VERSION = "garment-evidence-v1"
EVIDENCE_SCHEMA_VERSION = "garment-evidence-v1"


@dataclass(frozen=True)
class NormalizedImage:
    image_id: UUID
    jpeg_bytes: bytes
    sha256: str
    width: int
    height: int
    role: ImageRole


@dataclass(frozen=True)
class EvidenceProviderResult:
    delta: GarmentEvidenceDelta
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class BarcodeCandidate:
    """Untrusted printed digits located by a vision/OCR provider.

    The application normalizes and checksum-validates these before a catalog
    lookup.  A candidate is deliberately not evidence of garment identity.
    """

    image_id: UUID
    value: str


def decode_barcodes(images: tuple[NormalizedImage, ...]) -> tuple[BarcodeCandidate, ...]:
    """Decode 1D/2D barcode pixels locally; OCR is only a later fallback."""
    candidates: list[BarcodeCandidate] = []
    for image in images:
        try:
            with Image.open(BytesIO(image.jpeg_bytes)) as decoded:
                matches = zxingcpp.read_barcodes(decoded)
        except (OSError, ValueError):
            continue
        candidates.extend(
            BarcodeCandidate(image_id=image.image_id, value=match.text)
            for match in matches
            if match.valid and match.text
        )
    return tuple(candidates)


class VisionProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class VisionEvidenceProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...

    async def extract_evidence(
        self, images: tuple[NormalizedImage, ...], prior_dossier: object | None = None
    ) -> EvidenceProviderResult: ...

    async def extract_barcode_candidates(
        self, images: tuple[NormalizedImage, ...]
    ) -> tuple[BarcodeCandidate, ...]: ...
