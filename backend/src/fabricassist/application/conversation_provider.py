"""Independent contextual-conversation generation capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fabricassist.application.provider import ProviderDescriptor
from fabricassist.domain.conversations import AssistantMessageProposal, ConversationContext


@dataclass(frozen=True)
class ConversationProviderResult:
    proposal: AssistantMessageProposal
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None


class ConversationProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...

    async def answer(
        self,
        context: ConversationContext,
        user_text: str,
    ) -> ConversationProviderResult: ...
