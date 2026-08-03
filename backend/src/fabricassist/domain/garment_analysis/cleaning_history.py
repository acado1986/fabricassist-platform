"""Pure eligibility rules for exact-garment cleaning history."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from fabricassist.domain.garment_analysis.models import StrictModel


class ServiceLifecycleKind(StrEnum):
    PLANNED = "planned"
    PERFORMED = "performed"
    COMPLETED = "completed"


class CleaningOutcome(StrEnum):
    SUCCESSFUL = "successful"
    DAMAGING = "damaging"
    UNKNOWN = "unknown"


class GarmentServiceEvent(StrictModel):
    event_id: UUID
    garment_id: UUID
    exact_garment_confirmed: bool
    lifecycle_kind: ServiceLifecycleKind
    outcome: CleaningOutcome
    method: str = Field(min_length=1, max_length=80)
    water_temperature_c: int | None = Field(default=None, ge=10, le=95)
    cycle: str | None = Field(default=None, max_length=80)
    detergent_category: str | None = Field(default=None, max_length=120)
    detergent_text: str | None = Field(default=None, max_length=500)
    stain_products: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    drying_method: str | None = Field(default=None, max_length=80)
    ironing_method: str | None = Field(default=None, max_length=80)
    observed_effects: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    confirmed_by: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    detail_schema_version: str = Field(min_length=1, max_length=80)
    detail_snapshot: dict[str, object] = Field(default_factory=dict)
    invalidated: bool = False
    superseded_by_event_id: UUID | None = None

    @model_validator(mode="after")
    def planned_events_cannot_claim_results(self) -> GarmentServiceEvent:
        if (
            self.lifecycle_kind is ServiceLifecycleKind.PLANNED
            and self.outcome is not CleaningOutcome.UNKNOWN
        ):
            raise ValueError("planned service events cannot claim a cleaning outcome")
        return self


def eligible_history(events: tuple[GarmentServiceEvent, ...]) -> tuple[GarmentServiceEvent, ...]:
    return tuple(
        event
        for event in events
        if event.exact_garment_confirmed
        and event.lifecycle_kind in {ServiceLifecycleKind.PERFORMED, ServiceLifecycleKind.COMPLETED}
        and not event.invalidated
        and event.superseded_by_event_id is None
    )


def successful_history(events: tuple[GarmentServiceEvent, ...]) -> tuple[GarmentServiceEvent, ...]:
    return tuple(
        event for event in eligible_history(events) if event.outcome is CleaningOutcome.SUCCESSFUL
    )


def damaging_history(events: tuple[GarmentServiceEvent, ...]) -> tuple[GarmentServiceEvent, ...]:
    return tuple(
        event for event in eligible_history(events) if event.outcome is CleaningOutcome.DAMAGING
    )
