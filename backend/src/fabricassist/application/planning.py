"""Provider-neutral care planning boundary and deterministic local planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fabricassist.application.provider import ProviderDescriptor
from fabricassist.domain.care import Cleaning, ProposedCarePlan
from fabricassist.domain.evidence import GarmentEvidenceDossier


class CarePlanningProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...

    async def propose_plan(
        self, dossier: GarmentEvidenceDossier, violations: tuple[str, ...] = ()
    ) -> CarePlanningProviderResult: ...


@dataclass(frozen=True)
class CarePlanningProviderResult:
    proposal: ProposedCarePlan
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class MockCarePlanningProvider:
    """No-network planner that creates only a deliberately provisional proposal."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(provider="mock", model="deterministic-review-safe")

    async def propose_plan(
        self, dossier: GarmentEvidenceDossier, violations: tuple[str, ...] = ()
    ) -> CarePlanningProviderResult:
        _ = dossier, violations
        return CarePlanningProviderResult(
            proposal=ProposedCarePlan(
                classification="provisional",
                cleaning=Cleaning(method="unknown"),
                uncertainties=["care_label_facts_unknown"],
                follow_up_questions=["Please add a clear photo of the care label."],
            ),
            provider=self.descriptor.provider,
            model=self.descriptor.model,
            latency_ms=0,
        )
