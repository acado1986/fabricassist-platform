"""Deterministic routing from declared image metadata; no model classification."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from fabricassist.domain.evidence import ImageRole
from fabricassist.domain.garment_analysis.models import StrictModel


class ImageViewpoint(StrEnum):
    FRONT = "front"
    BACK = "back"
    SIDE = "side"
    DETAIL = "detail"
    UNKNOWN = "unknown"


class LabelScope(StrEnum):
    CARE = "care"
    COMPOSITION = "composition"
    COMBINED = "combined"
    UNKNOWN = "unknown"


class QualityState(StrEnum):
    USABLE = "usable"
    BORDERLINE = "borderline"
    UNUSABLE = "unusable"
    UNKNOWN = "unknown"


class AnalysisImage(StrictModel):
    image_id: UUID
    role: ImageRole
    viewpoint: ImageViewpoint = ImageViewpoint.UNKNOWN
    label_scope: LabelScope = LabelScope.UNKNOWN
    quality_state: QualityState = QualityState.UNKNOWN
    display_order: int = Field(ge=0, le=1000)


class RoutedImages(StrictModel):
    garment_inspection: tuple[UUID, ...] = ()
    label_extraction: tuple[UUID, ...] = ()
    stain_treatment: tuple[UUID, ...] = ()
    excluded: tuple[UUID, ...] = ()


def route_images(images: tuple[AnalysisImage, ...]) -> RoutedImages:
    """Route only explicit supported roles and omit unusable/unknown-role input."""
    garment: list[UUID] = []
    labels: list[UUID] = []
    stains: list[UUID] = []
    contextual_overview: UUID | None = None
    excluded: list[UUID] = []
    for image in sorted(images, key=lambda item: item.display_order):
        if image.quality_state is QualityState.UNUSABLE:
            excluded.append(image.image_id)
        elif image.role in {
            ImageRole.GARMENT_OVERVIEW,
            ImageRole.CONSTRUCTION_DETAIL,
            ImageRole.DAMAGE_CLOSEUP,
        }:
            garment.append(image.image_id)
            if image.role is ImageRole.GARMENT_OVERVIEW and contextual_overview is None:
                contextual_overview = image.image_id
        elif image.role is ImageRole.STAIN_CLOSEUP:
            garment.append(image.image_id)
            stains.append(image.image_id)
        elif image.role in {ImageRole.CARE_LABEL, ImageRole.COMPOSITION_LABEL}:
            labels.append(image.image_id)
        else:
            excluded.append(image.image_id)
    return RoutedImages(
        garment_inspection=tuple(garment),
        label_extraction=tuple(labels),
        stain_treatment=tuple(
            [
                *stains,
                *(() if contextual_overview is None or not stains else (contextual_overview,)),
            ]
        ),
        excluded=tuple(excluded),
    )
