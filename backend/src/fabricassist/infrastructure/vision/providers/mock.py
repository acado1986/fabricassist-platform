"""Deterministic no-network model adapter used by default."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from fabricassist.application.model_provider import ConversationProviderResult
from fabricassist.application.vision import (
    BarcodeCandidate,
    EvidenceProviderResult,
    NormalizedImage,
)
from fabricassist.domain.conversations import AssistantMessageProposal, ConversationContext
from fabricassist.domain.evidence import EvidenceSource, GarmentEvidenceDelta, Observation


class MockModelProviderAdapter:
    """Review-safe adapter implementing the same port as every live provider."""

    async def extract_evidence(
        self, images: tuple[NormalizedImage, ...], prior_dossier: object | None = None
    ) -> EvidenceProviderResult:
        _ = prior_dossier
        observations = [
            Observation(
                id=uuid5(NAMESPACE_URL, f"mock:{image.image_id}"),
                kind="image_received",
                value=image.role.value,
                confidence=100,
                source=EvidenceSource(image_id=image.image_id, role=image.role),
            )
            for image in images
        ]
        return EvidenceProviderResult(
            delta=GarmentEvidenceDelta(
                observations=observations, uncertainties=["care_label_facts_unknown"]
            ),
            provider="mock",
            model="deterministic-review-safe",
            latency_ms=0,
        )

    async def extract_barcode_candidates(
        self, images: tuple[NormalizedImage, ...]
    ) -> tuple[BarcodeCandidate, ...]:
        _ = images
        return ()

    async def answer(
        self, context: ConversationContext, user_text: str
    ) -> ConversationProviderResult:
        _ = (context, user_text)
        return ConversationProviderResult(
            proposal=AssistantMessageProposal(
                text="I can only confirm actions supported by the active validated care result.",
                uncertainties=["chat_mock_provider"],
                follow_up_questions=["Would you like to add a clear care-label photo?"],
            ),
            provider="mock",
            model="deterministic-conversation",
            latency_ms=0,
            input_tokens=None,
            output_tokens=None,
        )
