"""Versioned cache keys for the complete typed v2 result."""

from __future__ import annotations

import hashlib
import json

from fabricassist.domain.garment_analysis.models import FabricAssistAnalysisResult

CANONICAL_CACHE_VERSION = "canonical-plan-cache-v2"
RENDER_CACHE_VERSION = "rendered-answer-cache-v2"


def canonical_v2_signature(
    result: FabricAssistAnalysisResult,
    *,
    product_fingerprint: str | None,
) -> str:
    """Include all safety fields, product provenance, and active versions."""
    payload = {
        "version": CANONICAL_CACHE_VERSION,
        "result": result.model_dump(mode="json"),
        "product_fingerprint": product_fingerprint,
        "care_policy": result.care_policy.care_policy_version,
        "rendering": result.versions.get("rendering_template", "care-rendering-v2"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
