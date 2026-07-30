"""Adapter-owned typed job transport configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CeleryJobDispatcherConfig(BaseModel):
    """Non-secret Celery dispatch configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_name: str = "fabricassist.execute_analysis_job"


class QStashJobDispatcherConfig(BaseModel):
    """Outbound QStash configuration with redacted credentials."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: str = Field(repr=False)
    destination_url: str
    request_timeout_seconds: float = Field(gt=0, le=30)
    delivery_timeout_seconds: int = Field(ge=1, le=900)


class QStashVerifierConfig(BaseModel):
    """Inbound QStash signature policy with rotation-safe redaction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    current_signing_key: str = Field(repr=False)
    next_signing_key: str = Field(repr=False)
    destination_url: str
