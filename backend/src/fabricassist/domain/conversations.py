"""Strict, provider-neutral conversation contracts and context limits."""

from __future__ import annotations

# pyright: reportUnknownVariableType=false
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from fabricassist.domain.garment_analysis.models import CandidateClaim

CONVERSATION_SCHEMA_VERSION = "conversation-v1"
CONVERSATION_PROMPT_VERSION = "conversation-v1"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ActionableClaim(BaseModel):
    """A v2 candidate claim, deterministically gated before customer delivery."""

    model_config = ConfigDict(extra="forbid")

    claim: CandidateClaim


class AssistantMessageProposal(BaseModel):
    """Provider output; evidence text is untrusted and claims are typed separately."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = CONVERSATION_SCHEMA_VERSION
    text: str = Field(min_length=1, max_length=4_000)
    actionable_claims: list[ActionableClaim] = Field(default_factory=list, max_length=8)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=32)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=10)


class ConversationContext(BaseModel):
    """Bounded server-owned context sent to a provider, never provider history."""

    model_config = ConfigDict(extra="forbid")

    garment_id: UUID
    analysis_revision_id: UUID
    assessment: dict[str, object]
    care_policy: dict[str, object]
    recommendation: dict[str, object]
    validation_report: dict[str, object]
    service_history: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    summary: dict[str, object] | None = None
    recent_messages: list[dict[str, object]] = Field(default_factory=list, max_length=12)
    relevant_image_ids: list[UUID] = Field(default_factory=list, max_length=8)
