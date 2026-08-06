"""Deterministic routing from declared image metadata; no model classification."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

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


class ImageQualitySignals(StrictModel):
    """Version-neutral local signals used before any provider call."""

    state: QualityState = QualityState.UNKNOWN
    blur_score: float | None = Field(default=None, ge=0, le=1)
    brightness_score: float | None = Field(default=None, ge=0, le=1)
    contrast_score: float | None = Field(default=None, ge=0, le=1)
    glare_score: float | None = Field(default=None, ge=0, le=1)
    crop_readability_score: float | None = Field(default=None, ge=0, le=1)
    orientation_degrees: int | None = Field(default=None)

    @model_validator(mode="after")
    def orientation_is_normalized(self) -> ImageQualitySignals:
        if self.orientation_degrees is not None and self.orientation_degrees not in {
            0,
            90,
            180,
            270,
        }:
            raise ValueError("orientation_degrees must be one of 0, 90, 180, or 270")
        return self


class AnalysisImage(StrictModel):
    image_id: UUID
    role: ImageRole
    viewpoint: ImageViewpoint = ImageViewpoint.UNKNOWN
    label_scope: LabelScope = LabelScope.UNKNOWN
    quality_state: QualityState = QualityState.UNKNOWN
    blur_score: float | None = Field(default=None, ge=0, le=1)
    brightness_score: float | None = Field(default=None, ge=0, le=1)
    contrast_score: float | None = Field(default=None, ge=0, le=1)
    glare_score: float | None = Field(default=None, ge=0, le=1)
    crop_readability_score: float | None = Field(default=None, ge=0, le=1)
    orientation_degrees: int | None = Field(default=None)
    display_order: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def metadata_matches_role(self) -> AnalysisImage:
        if self.viewpoint is not ImageViewpoint.UNKNOWN and self.role not in {
            ImageRole.GARMENT_OVERVIEW,
            ImageRole.CONSTRUCTION_DETAIL,
        }:
            raise ValueError("viewpoint is only valid for garment or construction views")
        if self.label_scope is not LabelScope.UNKNOWN and self.role not in {
            ImageRole.CARE_LABEL,
            ImageRole.COMPOSITION_LABEL,
        }:
            raise ValueError("label_scope is only valid for label images")
        if self.orientation_degrees is not None and self.orientation_degrees not in {
            0,
            90,
            180,
            270,
        }:
            raise ValueError("orientation_degrees must be one of 0, 90, 180, or 270")
        return self


class RoutedImages(StrictModel):
    garment_inspection: tuple[UUID, ...] = ()
    label_extraction: tuple[UUID, ...] = ()
    barcode_enrichment: tuple[UUID, ...] = ()
    stain_treatment: tuple[UUID, ...] = ()
    excluded: tuple[UUID, ...] = ()


def route_images(images: tuple[AnalysisImage, ...]) -> RoutedImages:
    """Route only explicit supported roles and omit unusable/unknown-role input."""
    garment: list[UUID] = []
    labels: list[UUID] = []
    barcodes: list[UUID] = []
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
        elif image.role is ImageRole.BARCODE_BRAND_LABEL:
            barcodes.append(image.image_id)
        else:
            excluded.append(image.image_id)
    return RoutedImages(
        garment_inspection=tuple(garment),
        label_extraction=tuple(labels),
        barcode_enrichment=tuple(barcodes),
        stain_treatment=tuple(
            [
                *stains,
                *(() if contextual_overview is None or not stains else (contextual_overview,)),
            ]
        ),
        excluded=tuple(excluded),
    )
