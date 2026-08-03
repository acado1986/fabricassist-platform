"""Small deterministic image-quality adapter used at upload completion."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from statistics import mean, pvariance
from typing import cast

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ImageQualityAssessment:
    state: str
    blur_score: float
    brightness_score: float
    contrast_score: float
    glare_score: float
    crop_readability_score: float
    orientation_degrees: int


@dataclass(frozen=True)
class ImageQualityThresholds:
    """Configurable policy inputs; the defaults are intentionally conservative."""

    minimum_dimension: int = 320
    borderline_blur: float = 0.03
    borderline_contrast: float = 0.05
    minimum_brightness: float = 0.06
    maximum_brightness: float = 0.97
    borderline_glare: float = 0.35
    minimum_readability: float = 0.05


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _orientation_degrees(image: Image.Image) -> int:
    orientation = image.getexif().get(274, 1)
    return {3: 180, 6: 90, 8: 270}.get(int(orientation), 0)


def assess_image_quality(
    raw: bytes, thresholds: ImageQualityThresholds | None = None
) -> ImageQualityAssessment:
    """Return conservative local signals without classifying the image's semantic role."""

    policy = thresholds or ImageQualityThresholds()
    with Image.open(BytesIO(raw)) as source:
        orientation = _orientation_degrees(source)
        image = ImageOps.exif_transpose(source).convert("L")
        original_width, original_height = image.size
        image.thumbnail((128, 128))
        pixels = [float(value) for value in cast(list[int], list(image.get_flattened_data()))]
        width, height = image.size

    if not pixels:
        raise ValueError("IMAGE_EMPTY")
    brightness = _bounded(mean(pixels) / 255.0)
    contrast = _bounded((pvariance(pixels) ** 0.5) / 64.0)

    # A small Laplacian variance is a useful blur warning and is deterministic
    # without adding OpenCV or NumPy to the upload path.
    laplacians: list[float] = []
    if width > 2 and height > 2:
        for y in range(1, height - 1):
            row = y * width
            for x in range(1, width - 1):
                center = pixels[row + x]
                laplacians.append(
                    float(
                        4 * center
                        - pixels[row + x - 1]
                        - pixels[row + x + 1]
                        - pixels[row - width + x]
                        - pixels[row + width + x]
                    )
                )
    glare = _bounded(sum(pixel >= 250 for pixel in pixels) / len(pixels))
    blur = _bounded((pvariance(laplacians) ** 0.5) / 96.0) if laplacians else 0.0
    readability = _bounded(contrast * (1.0 - glare))

    # Only hard safety bounds reject input. Borderline visual signals are
    # persisted for the later branch-specific policy and user guidance.
    if original_width < policy.minimum_dimension or original_height < policy.minimum_dimension:
        state = "unusable"
    elif (
        blur < policy.borderline_blur
        or contrast < policy.borderline_contrast
        or brightness < policy.minimum_brightness
        or brightness > policy.maximum_brightness
        or glare >= policy.borderline_glare
        or readability < policy.minimum_readability
    ):
        state = "borderline"
    else:
        state = "usable"
    return ImageQualityAssessment(
        state=state,
        blur_score=blur,
        brightness_score=brightness,
        contrast_score=contrast,
        glare_score=glare,
        crop_readability_score=readability,
        orientation_degrees=orientation,
    )
