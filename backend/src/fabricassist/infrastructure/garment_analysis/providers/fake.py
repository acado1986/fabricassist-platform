"""Deterministic, no-network provider for garment-analysis contract tests."""

from __future__ import annotations

from typing import Any

from fabricassist.application.garment_analysis import (
    BarcodeEnrichmentRequest,
    GarmentInspectionRequest,
    LabelExtractionRequest,
    ModelInvocation,
    StainTreatmentRequest,
    load_prompt,
)
from fabricassist.domain.garment_analysis.models import (
    GarmentInspection,
    LabelExtraction,
    StainTreatment,
)
from fabricassist.domain.garment_analysis.parity import BarcodeEnrichment


class FakeGarmentVisionProvider:
    """Produces schema-valid unknown results; never substitutes safety facts."""

    provider = "mock"
    model = "deterministic-garment-analysis"

    async def inspect_garment(
        self, request: GarmentInspectionRequest
    ) -> ModelInvocation[GarmentInspection]:
        return self._invocation(
            "garment_inspection",
            GarmentInspection(overall_confidence=0, uncertain_fields=("garment_unknown",)),
            request.attempt_number,
        )

    async def extract_labels(
        self, request: LabelExtractionRequest
    ) -> ModelInvocation[LabelExtraction]:
        return self._invocation(
            "label_extraction",
            LabelExtraction(overall_confidence=0, uncertain_symbols=("label_unknown",)),
            request.attempt_number,
        )

    async def analyze_stain(
        self, request: StainTreatmentRequest
    ) -> ModelInvocation[StainTreatment]:
        from uuid import NAMESPACE_URL, uuid5

        return self._invocation(
            "stain_treatment",
            StainTreatment(
                treatment_id=uuid5(NAMESPACE_URL, "fake-stain"),
                overall_confidence=0,
                uncertainty=("stain_unknown",),
            ),
            request.attempt_number,
        )

    async def extract_barcode_candidates(
        self, request: BarcodeEnrichmentRequest
    ) -> ModelInvocation[BarcodeEnrichment]:
        return self._invocation(
            "barcode_enrichment",
            BarcodeEnrichment(warnings=("barcode_not_decoded",)),
            request.attempt_number,
        )

    def _invocation(self, branch: str, value: Any, attempt_number: int) -> ModelInvocation[Any]:
        asset = load_prompt(branch)
        return ModelInvocation(
            value=value,
            provider=self.provider,
            model=self.model,
            prompt_version=asset.version,
            prompt_checksum=asset.checksum,
            schema_version=value.schema_version,
            latency_ms=0,
            attempt_number=attempt_number,
        )
