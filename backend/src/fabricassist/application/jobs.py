"""Provider-neutral asynchronous analysis dispatch contracts."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

type AnalysisStage = Literal["validate_uploaded_images", "execute_analysis"]
ANALYSIS_STAGES: tuple[AnalysisStage, ...] = (
    "validate_uploaded_images",
    "execute_analysis",
)


class AnalysisJobMessage(BaseModel):
    """Identifier-only, versioned message accepted by the future job executor."""

    model_config = ConfigDict(extra="forbid", strict=True)

    message_schema_version: Literal[1] = 1
    scan_id: UUID
    operation_key: str = Field(min_length=1, max_length=255)
    # Celery executes the same application use case in-process; QStash uses
    # these bounded transport checkpoints without duplicating business rules.
    stage: AnalysisStage
    revision_id: UUID


class ConversationJobMessage(BaseModel):
    """Identifier-only message for an already-durable conversation request."""

    model_config = ConfigDict(extra="forbid", strict=True)

    message_schema_version: Literal[1] = 1
    conversation_message_id: UUID


type JobMessage = AnalysisJobMessage | ConversationJobMessage


class JobDispatchError(RuntimeError):
    """Transport-neutral publication failure without private delivery details."""


class RetryableJobDispatchError(JobDispatchError):
    """A temporary publication failure that recovery may retry."""


class PermanentJobDispatchError(JobDispatchError):
    """A publication failure that retries cannot repair."""


class JobDispatcher(Protocol):
    """Dispatch an immutable analysis-job envelope without owning business state."""

    async def dispatch_analysis(
        self, message: AnalysisJobMessage, *, correlation_id: str
    ) -> None: ...

    async def dispatch_conversation(
        self,
        message: ConversationJobMessage,
        *,
        correlation_id: str,
    ) -> None: ...


class ConversationJobDispatcher(Protocol):
    """Dispatch a durable conversation request without transport knowledge."""

    async def dispatch_conversation(
        self,
        message: ConversationJobMessage,
        *,
        correlation_id: str,
    ) -> None: ...
