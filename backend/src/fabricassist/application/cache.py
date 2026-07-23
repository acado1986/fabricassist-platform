"""Versioned, tenant-scoped durable cache helpers for garment analysis.

PostgreSQL entries are authoritative.  Perceptual hashes are discovery-only:
callers must still compare every versioned exact safety field before reuse.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from io import BytesIO
from typing import Any, cast

from PIL import Image

from fabricassist.application.vision import (
    EVIDENCE_PROMPT_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    NormalizedImage,
)
from fabricassist.domain.care import CareValidationReport, ProposedCarePlan
from fabricassist.domain.evidence import GarmentEvidenceDossier, ImageRole

NORMALIZATION_VERSION = "normalized-jpeg-v1"


def perceptual_hash(image: NormalizedImage) -> str:
    """Return a deterministic 64-bit aHash; it is never a reuse key."""
    with Image.open(BytesIO(image.jpeg_bytes)) as decoded:
        grayscale: object = cast(Any, decoded).convert("L").resize((8, 8))
        pixels = [int(value) for value in cast(Iterable[int], cast(Any, grayscale).getdata())]
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if value >= mean else "0" for value in pixels)
    return f"{int(bits, 2):016x}"


def evidence_cache_key(image: NormalizedImage) -> str:
    return ":".join(
        (
            "fabricassist",
            "evidence",
            NORMALIZATION_VERSION,
            EVIDENCE_SCHEMA_VERSION,
            EVIDENCE_PROMPT_VERSION,
            image.role.value,
            image.sha256,
        )
    )


def canonical_plan_signature(
    dossier: GarmentEvidenceDossier,
    proposal: ProposedCarePlan,
    report: CareValidationReport,
    product_fingerprint: str | None,
) -> str:
    """Hash all safety-relevant data and every release/rendering version."""
    material = {
        "dossier": dossier.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json"),
        "validation": report.model_dump(mode="json"),
        "product_fingerprint": product_fingerprint,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_prompt_version": EVIDENCE_PROMPT_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def product_snapshot_fingerprint(snapshot: dict[str, object] | None) -> str | None:
    if snapshot is None:
        return None
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def relevant_phash_roles(role: ImageRole) -> tuple[ImageRole, ...]:
    """Restrict candidate discovery to equal evidence roles; never auto-reuse it."""
    return (role,)


def uncached_images(
    images: Iterable[NormalizedImage], cached_hashes: set[tuple[str, str]]
) -> tuple[NormalizedImage, ...]:
    return tuple(image for image in images if (image.sha256, image.role.value) not in cached_hashes)


async def upsert_exact_evidence_cache_entry(session: object, values: dict[str, object]) -> None:
    """Persist one exact entry safely when two workers race for the same image.

    The first valid extraction remains the durable value; a racing worker only
    increments provenance. Fake unit sessions deliberately use the simple path.
    """
    from datetime import UTC, datetime

    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy.ext.asyncio import AsyncSession

    from fabricassist.infrastructure.persistence.models import EvidenceCacheEntry

    if not isinstance(session, AsyncSession):
        session.add(EvidenceCacheEntry(**values))  # type: ignore[union-attr]
        return
    statement = (
        insert(EvidenceCacheEntry)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_evidence_cache_exact_versioned",
            set_={
                "reuse_count": EvidenceCacheEntry.reuse_count + 1,
                "last_reused_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(statement)
