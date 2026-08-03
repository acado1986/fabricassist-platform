"""Composition root for the one supported garment-analysis executor."""

from __future__ import annotations

from fabricassist.application.garment_analysis import (
    AsyncioGarmentAnalysisWorkflow,
    GarmentAnalysisWorkflowPolicy,
)
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.garment_analysis.assets import SqlAlchemyRevisionImageAssets
from fabricassist.infrastructure.garment_analysis.persistence import (
    SqlAlchemyGarmentAnalysisBranchStore,
    SqlAlchemyGarmentAnalysisFinalizationStore,
)
from fabricassist.infrastructure.garment_analysis.providers import create_garment_vision_provider
from fabricassist.settings import Settings


def create_garment_analysis_workflow(
    *, database: Database, storage: ObjectStorage, settings: Settings
) -> AsyncioGarmentAnalysisWorkflow:
    """Compose v2 only; callers never have a legacy executor fallback."""
    return AsyncioGarmentAnalysisWorkflow(
        branch_repository=SqlAlchemyGarmentAnalysisBranchStore(database.session_factory),
        image_repository=SqlAlchemyRevisionImageAssets(database.session_factory, storage),
        provider=create_garment_vision_provider(settings),
        finalization_repository=SqlAlchemyGarmentAnalysisFinalizationStore(
            database.session_factory
        ),
        policy=GarmentAnalysisWorkflowPolicy(
            lease_seconds=settings.worker_concurrency_lease_seconds,
            branch_timeout_seconds=settings.vision_timeout_seconds,
            stain_analysis_enabled=settings.garment_analysis_stain_enabled,
        ),
    )
