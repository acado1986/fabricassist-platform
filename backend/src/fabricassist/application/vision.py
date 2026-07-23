"""Application port for source-referenced evidence extraction."""
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

import zxingcpp
from PIL import Image

from fabricassist.domain.evidence import EvidenceSource, GarmentEvidenceDelta, ImageRole

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
    async def extract_evidence(
        self, images: tuple[NormalizedImage, ...], prior_dossier: object | None = None
    ) -> EvidenceProviderResult: ...

    async def extract_barcode_candidates(
        self, images: tuple[NormalizedImage, ...]
    ) -> tuple[BarcodeCandidate, ...]: ...


class MockVisionProvider:
    """No-network provider: it intentionally returns unknown, review-safe evidence."""

    async def extract_evidence(
        self, images: tuple[NormalizedImage, ...], prior_dossier: object | None = None
    ) -> EvidenceProviderResult:
        _ = prior_dossier
        observations = []
        for image in images:
            observations.append(
                {
                    "id": uuid5(NAMESPACE_URL, f"mock:{image.image_id}"),
                    "kind": "image_received",
                    "value": image.role.value,
                    "confidence": 100,
                    "source": EvidenceSource(image_id=image.image_id, role=image.role),
                }
            )
        return EvidenceProviderResult(
            delta=GarmentEvidenceDelta(
                observations=observations, uncertainties=["care_label_facts_unknown"]
            ),
            provider="mock",
            model="deterministic-review-safe",
            latency_ms=0,
        )

    async def extract_barcode_candidates(
        self, images: tuple[NormalizedImage, ...]
    ) -> tuple[BarcodeCandidate, ...]:
        # The default local provider never fabricates digits from pixels. Live
        # adapters may use OCR solely to recover candidates for validation.
        _ = images
        return ()
