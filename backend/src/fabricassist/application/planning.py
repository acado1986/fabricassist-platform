"""Provider-neutral care planning boundary and deterministic local planner."""

from __future__ import annotations

from typing import Protocol

from fabricassist.domain.care import Cleaning, ProposedCarePlan
from fabricassist.domain.evidence import GarmentEvidenceDossier


class CarePlanningProvider(Protocol):
    async def propose_plan(
        self, dossier: GarmentEvidenceDossier, violations: tuple[str, ...] = ()
    ) -> ProposedCarePlan: ...


class MockCarePlanningProvider:
    """No-network planner that creates only a deliberately provisional proposal."""

    async def propose_plan(
        self, dossier: GarmentEvidenceDossier, violations: tuple[str, ...] = ()
    ) -> ProposedCarePlan:
        _ = dossier, violations
        return ProposedCarePlan(
            classification="provisional",
            cleaning=Cleaning(method="unknown"),
            uncertainties=["care_label_facts_unknown"],
            follow_up_questions=["Please add a clear photo of the care label."],
        )
