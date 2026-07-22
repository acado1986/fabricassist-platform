"""Configured evidence provider registry; live adapters are deferred behind this port."""

from fabricassist.application.vision import MockVisionProvider, VisionEvidenceProvider
from fabricassist.settings import Settings

PROMPT_VERSION = "garment-evidence-v1"
SCHEMA_VERSION = "garment-evidence-v1"


def get_vision_provider(settings: Settings) -> VisionEvidenceProvider:
    if settings.vision_provider != "mock":
        raise RuntimeError("A live evidence adapter is not configured for this release")
    return MockVisionProvider()
