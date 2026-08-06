"""Provider-free localized rendering for the validated v2 result."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from fabricassist.domain.garment_analysis.models import FabricAssistAnalysisResult
from fabricassist.domain.garment_analysis.parity import RenderedAnswerProjection

_TITLE = {"en": "Validated care guidance", "es": "Guía de cuidado validada"}
_OUTCOME = {
    "en": {
        "passed": "Validated for release",
        "passed_with_warnings": "Validated with important notes",
        "needs_better_image": "A clearer photo is needed",
        "needs_review": "A care specialist needs to review this",
        "blocked": "Care guidance cannot be safely released yet",
    },
    "es": {
        "passed": "Validado para mostrar",
        "passed_with_warnings": "Validado con indicaciones importantes",
        "needs_better_image": "Se necesita una foto más clara",
        "needs_review": "Un especialista debe revisar este caso",
        "blocked": "Las indicaciones aún no se pueden mostrar de forma segura",
    },
}


def render_v2_answer(
    *, result_id: UUID, result: FabricAssistAnalysisResult, language: str, template_version: str
) -> RenderedAnswerProjection:
    """Render only typed, already validated claims; never call a model."""
    if language not in {"en", "es"}:
        raise ValueError("unsupported rendering language")
    assessment = result.assessment
    sections = {
        "title": _TITLE[language],
        "validation_state": _OUTCOME[language].get(
            result.care_policy.outcome.value, result.care_policy.outcome.value
        ),
        "outcome": result.care_policy.outcome.value,
        "allowed_actions": [
            action.model_dump(mode="json") for action in result.care_policy.allowed_actions
        ],
        "prohibited_actions": [
            action.model_dump(mode="json") for action in result.care_policy.prohibited_actions
        ],
        "unknown_actions": [
            action.model_dump(mode="json") for action in result.care_policy.unknown_actions
        ],
        "professional_only_actions": [
            action.model_dump(mode="json")
            for action in result.care_policy.professional_only_actions
        ],
        "warnings": list(result.care_policy.warnings),
        "uncertainties": list(assessment.uncertainties),
        "product": (
            {
                "barcode": assessment.product_barcode,
                "status": assessment.product_lookup_status,
                "source": assessment.product_source,
                "facts": assessment.product_facts.model_dump(mode="json")
                if assessment.product_facts is not None
                else None,
            }
            if assessment.product_barcode is not None
            else None
        ),
        "source_summary": {
            "photographed_label": bool(assessment.label_extraction),
            "product_lookup": assessment.product_lookup_status,
            "inferred_visual": assessment.garment_inspection is not None,
        },
    }
    return RenderedAnswerProjection(
        result_id=result_id,
        language=language,
        template_version=template_version,
        validation_outcome=result.care_policy.outcome.value,
        sections=cast(dict[str, JsonValue], sections),
        provenance=tuple(
            item
            for item in (
                "photographed_label" if assessment.label_extraction else "",
                "verified_lookup" if assessment.product_barcode else "",
                "visual_inference" if assessment.garment_inspection else "",
            )
            if item
        ),
        rendered_at=datetime.now(UTC),
    )
