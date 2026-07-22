"""Typed AI proposal and deterministic safety release gate."""

from __future__ import annotations

# pyright: reportUnknownVariableType=false
import hashlib
import json
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from fabricassist.domain.evidence import GarmentEvidenceDossier

POLICY_VERSION = "care-validation-v1"
POLICY_PATH = Path(__file__).with_name("care_policy_v1.json")
POLICY_CHECKSUM = (
    hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest() if POLICY_PATH.exists() else "unavailable"
)


class ValidationOutcome(StrEnum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    BLOCKED = "blocked"
    NEEDS_BETTER_IMAGE = "needs_better_image"
    NEEDS_REVIEW = "needs_review"


class Cleaning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str = Field(pattern="^(water_wash|professional_dry_clean|unknown)$")
    maximum_temperature_c: int | None = Field(default=None, ge=10, le=95)


class ProposedCarePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "proposed-care-plan-v1"
    classification: str = Field(pattern="^(definitive|provisional)$")
    preparation: list[str] = Field(default_factory=list)
    stain_guidance: list[str] = Field(default_factory=list)
    cleaning: Cleaning
    detergent: str = Field(default="no_domestic_detergent")
    drying: list[str] = Field(default_factory=list)
    ironing: list[str] = Field(default_factory=list)
    professional_care: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class CareValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: ValidationOutcome
    policy_version: str = POLICY_VERSION
    policy_checksum: str = POLICY_CHECKSUM
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    repairable: bool = False


def validate_care_plan(
    dossier: GarmentEvidenceDossier, proposal: ProposedCarePlan
) -> CareValidationReport:
    """Validate a proposal, never create or substitute one."""
    violations: list[str] = []
    warnings: list[str] = []
    wash = dossier.fact("wash")
    dry_clean = dossier.fact("dry_clean")
    sensitive = any(item.kind in {"leather", "suede", "fur"} for item in dossier.observations)
    has_label = any(fact.source.role.value == "care_label" for fact in dossier.care_facts)
    if not has_label and proposal.classification != "provisional":
        violations.append("GARMENT_ONLY_MUST_BE_PROVISIONAL")
    if not has_label and proposal.cleaning.method != "unknown":
        violations.append("GARMENT_ONLY_CANNOT_AUTHORIZE_CLEANING")
    if wash and wash.permission == "prohibited":
        if (
            proposal.cleaning.method == "water_wash"
            or proposal.detergent != "no_domestic_detergent"
        ):
            violations.append("LABEL_PROHIBITS_WATER_WASH")
    if (
        wash
        and wash.temperature_c
        and proposal.cleaning.maximum_temperature_c
        and proposal.cleaning.maximum_temperature_c > wash.temperature_c
    ):
        violations.append("WASH_TEMPERATURE_EXCEEDS_LABEL")
    if (
        dry_clean
        and dry_clean.permission == "prohibited"
        and proposal.cleaning.method == "professional_dry_clean"
    ):
        violations.append("LABEL_PROHIBITS_DRY_CLEAN")
    if any(
        "solvent" in action.lower() for action in [*proposal.preparation, *proposal.stain_guidance]
    ):
        violations.append("NO_CONSUMER_PROFESSIONAL_SOLVENTS")
    if sensitive:
        warnings.append("SENSITIVE_MATERIAL_REQUIRES_REVIEW")
    if violations:
        return CareValidationReport(
            outcome=ValidationOutcome.BLOCKED, violations=violations, repairable=True
        )
    if sensitive:
        return CareValidationReport(outcome=ValidationOutcome.NEEDS_REVIEW, warnings=warnings)
    if dossier.uncertainties:
        return CareValidationReport(
            outcome=ValidationOutcome.PASSED_WITH_WARNINGS, warnings=dossier.uncertainties
        )
    return CareValidationReport(outcome=ValidationOutcome.PASSED)


def policy_document() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text())
