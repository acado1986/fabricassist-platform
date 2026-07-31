"""Request-scoped GraphQL loaders over application query ports."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from strawberry.dataloader import DataLoader

from fabricassist.application.storefront_queries import (
    AnalysisRevisionView,
    GarmentView,
    ImageMetadataView,
    RunView,
    ScanView,
    StorefrontPrincipal,
    StorefrontQueryPort,
)


class GraphQLLoaders:
    """Loader instances are created for one authenticated GraphQL request."""

    def __init__(self, query_port: StorefrontQueryPort, principal: StorefrontPrincipal) -> None:
        async def scans(keys: list[object]) -> list[ScanView | None]:
            typed_keys = cast(list[UUID], keys)
            values = await query_port.get_scans(principal, typed_keys)
            return [values.get(key) for key in typed_keys]

        async def garments(keys: list[object]) -> list[GarmentView | None]:
            typed_keys = cast(list[UUID], keys)
            values = await query_port.get_garments(principal, typed_keys)
            return [values.get(key) for key in typed_keys]

        async def revisions(keys: list[object]) -> list[AnalysisRevisionView | None]:
            typed_keys = cast(list[UUID], keys)
            values = await query_port.get_analysis_revisions(principal, typed_keys)
            return [values.get(key) for key in typed_keys]

        async def images(keys: list[object]) -> list[list[ImageMetadataView] | None]:
            typed_keys = cast(list[UUID], keys)
            values = await query_port.get_images_metadata(principal, typed_keys)
            return [values.get(key) for key in typed_keys]

        async def runs(keys: list[object]) -> list[RunView | None]:
            typed_keys = cast(list[UUID], keys)
            values = await query_port.get_runs(principal, typed_keys)
            return [values.get(key) for key in typed_keys]

        self.scans = DataLoader(load_fn=scans)
        self.garments = DataLoader(load_fn=garments)
        self.revisions = DataLoader(load_fn=revisions)
        self.images = DataLoader(load_fn=images)
        self.runs = DataLoader(load_fn=runs)
