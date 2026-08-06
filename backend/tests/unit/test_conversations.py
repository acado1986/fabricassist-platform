from typing import cast
from uuid import uuid4

import pytest

from fabricassist.api.routes.conversations import string_items
from fabricassist.application.conversations import answer_message, select_relevant_image_ids
from fabricassist.application.policies import ConversationPolicy
from fabricassist.domain.conversations import (
    AssistantMessageProposal,
    ConversationContext,
)
from fabricassist.domain.garment_analysis.models import CandidateClaim
from fabricassist.infrastructure.persistence.models import (
    ConversationMessage,
    ModelRun,
    ScanImage,
)


def test_structured_chat_claim_rejects_untyped_action() -> None:
    proposal = AssistantMessageProposal(text="Safe explanation")
    assert proposal.actionable_claims == []
    claim = CandidateClaim(claim_id=uuid4(), action_code="water_wash", text="Wash gently")
    structured = AssistantMessageProposal.model_validate(
        {
            "text": "x",
            "actionable_claims": [{"claim": claim.model_dump(mode="json")}],
            "evidence_ids": [str(uuid4())],
        }
    )
    assert structured.actionable_claims[0].claim.action_code == "water_wash"


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


def test_message_response_items_accept_legacy_array_defaults() -> None:
    assert string_items([]) == []
    assert string_items({"items": ["label unclear", 123]}) == ["label unclear"]


@pytest.mark.asyncio
async def test_duplicate_conversation_delivery_creates_one_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = ConversationMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        thread_id=uuid4(),
        scan_id=uuid4(),
        garment_id=uuid4(),
        role="user",
        status="queued",
        text="Can I wash this?",
        analysis_revision_id=uuid4(),
        care_result_id=uuid4(),
        dispatch_correlation_id=str(uuid4()),
    )
    added: list[object] = []

    class Session:
        scalar_calls = 0

        async def scalar(self, _statement: object) -> object:
            self.scalar_calls += 1
            return user if self.scalar_calls in {1, 3} else 1

        def add(self, value: object) -> None:
            added.append(value)

        async def flush(self) -> None:
            pass

        async def commit(self) -> None:
            pass

    context = ConversationContext(
        garment_id=user.garment_id,
        analysis_revision_id=user.analysis_revision_id,
        assessment={},
        care_policy={
            "care_policy_version": "care-policy-v2",
            "policy_checksum": "test",
            "outcome": "passed",
        },
        recommendation={"recommendation_id": str(uuid4()), "preference_source": "generic_policy"},
        validation_report={},
    )

    async def context_for(*_args: object) -> ConversationContext:
        return context

    monkeypatch.setattr(
        "fabricassist.application.conversations.build_context",
        context_for,
    )
    calls = 0

    class Provider:
        @property
        def descriptor(self):
            from fabricassist.application.provider import ProviderDescriptor

            return ProviderDescriptor("mock", "chat")

        async def answer(self, _context: ConversationContext, _text: str):
            from fabricassist.application.conversation_provider import (
                ConversationProviderResult,
            )

            nonlocal calls
            calls += 1
            return ConversationProviderResult(
                proposal=AssistantMessageProposal(text="Add a clear label photo."),
                provider="mock",
                model="chat",
                latency_ms=0,
                input_tokens=None,
                output_tokens=None,
            )

    session = Session()
    policy = ConversationPolicy(recent_message_limit=12, relevant_image_limit=8)
    await answer_message(
        session,  # type: ignore[arg-type]
        user.id,
        Provider(),  # type: ignore[arg-type]
        policy,
    )
    await answer_message(
        session,  # type: ignore[arg-type]
        user.id,
        Provider(),  # type: ignore[arg-type]
        policy,
    )

    assistants = [
        value
        for value in added
        if isinstance(value, ConversationMessage) and value.role == "assistant"
    ]
    assert calls == 1
    assert len(assistants) == 1
    assert sum(isinstance(value, ModelRun) for value in added) == 1
