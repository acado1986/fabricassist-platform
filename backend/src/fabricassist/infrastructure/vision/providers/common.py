"""Provider-neutral helpers shared by isolated model adapters."""

from __future__ import annotations

from fabricassist.application.vision import NormalizedImage
from fabricassist.domain.evidence import GarmentEvidenceDelta


def validate_sources(delta: GarmentEvidenceDelta, images: tuple[NormalizedImage, ...]) -> None:
    """Reject a model response that attributes a fact to a non-requested image."""
    permitted = {(image.image_id, image.role) for image in images}
    for item in [*delta.observations, *delta.care_facts]:
        if (item.source.image_id, item.source.role) not in permitted:
            raise ValueError("Evidence source does not match a supplied image")


def optional_int(value: object) -> int | None:
    """Return genuine integer token counters while rejecting booleans."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None
