from typing import cast
from uuid import uuid4

from fabricassist.application.conversations import select_relevant_image_ids
from fabricassist.domain.care import Cleaning, ProposedCarePlan
from fabricassist.domain.conversations import AssistantMessageProposal
from fabricassist.infrastructure.persistence.models import ScanImage


def test_structured_chat_claim_rejects_untyped_action() -> None:
    proposal = AssistantMessageProposal(text="Safe explanation")
    assert proposal.actionable_claims == []
    claim = ProposedCarePlan(classification="provisional", cleaning=Cleaning(method="unknown"))
    structured = AssistantMessageProposal.model_validate(
        {
            "text": "x",
            "actionable_claims": [{"plan": claim.model_dump(mode="json")}],
            "evidence_ids": [str(uuid4())],
        }
    )
    assert structured.actionable_claims[0].plan.cleaning.method == "unknown"


def test_relevant_images_prioritize_the_questioned_evidence_role() -> None:
    class Image:
        def __init__(self, role: str) -> None:
            self.id = uuid4()
            self.role = role

    label = Image("care_label")
    stain = Image("stain_closeup")
    overview = Image("garment_overview")
    selected = select_relevant_image_ids(
        cast(list[ScanImage], [overview, label, stain]), "Is this stain safe to treat?"
    )
    assert selected[:2] == [
        stain.id,
        label.id,
    ]
