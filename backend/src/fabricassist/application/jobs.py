"""Provider-neutral asynchronous analysis dispatch contracts."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisJobMessage(BaseModel):
    """Identifier-only, versioned message accepted by the future job executor."""

    model_config = ConfigDict(extra="forbid", strict=True)

    message_schema_version: Literal[1] = 1
    scan_id: UUID
    operation_key: str = Field(min_length=1, max_length=255)
    stage: Literal["validate_uploaded_images"]
    revision_id: UUID


class JobDispatcher(Protocol):
    """Dispatch an immutable analysis-job envelope without owning business state."""

    async def dispatch_analysis(
        self, message: AnalysisJobMessage, *, correlation_id: str
    ) -> None: ...
