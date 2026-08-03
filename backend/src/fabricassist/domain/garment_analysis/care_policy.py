"""Versioned deterministic safety envelope and candidate-claim gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from fabricassist.domain.garment_analysis.cleaning_history import (
    GarmentServiceEvent,
    damaging_history,
    successful_history,
)
from fabricassist.domain.garment_analysis.models import (
    CandidateClaim,
    CareAction,
    CarePolicy,
    CareRecommendation,
    ClaimValidationReport,
    ConflictSeverity,
    MergedGarmentAssessment,
    Permission,
    ValidationOutcome,
)

_POLICY_DIR = Path(__file__).with_name("policies")
CARE_POLICY_VERSION = "care-policy-v2"


def _asset_checksum(filename: str) -> str:
    return hashlib.sha256((_POLICY_DIR / filename).read_bytes()).hexdigest()


class CarePolicyRegistry:
    """Loads reviewed repository policy assets and exposes their immutable checksum."""

    def __init__(self, policy_dir: Path = _POLICY_DIR) -> None:
        self._policy_dir = policy_dir

    def document(self, version: str = CARE_POLICY_VERSION) -> dict[str, object]:
        path = self._policy_dir / f"{version}.json"
        if not path.is_file():
            raise ValueError(f"unknown care policy version: {version}")
        document = json.loads(path.read_text())
        if document.get("version") != version:
            raise ValueError("policy file version does not match activated policy version")
        return document

    def checksum(self, version: str = CARE_POLICY_VERSION) -> str:
        path = self._policy_dir / f"{version}.json"
        if not path.is_file():
            raise ValueError(f"unknown care policy version: {version}")
        return hashlib.sha256(path.read_bytes()).hexdigest()


_POLICY_REGISTRY = CarePolicyRegistry()


def _action(
    code: str,
    permission: Permission,
    *,
    reason: str,
    maximum_temperature_c: int | None = None,
    process: str | None = None,
    professional_only: bool = False,
) -> CareAction:
    return CareAction(
        code=code,
        permission=permission,
        maximum_temperature_c=maximum_temperature_c,
        process=process,
        reason_key=reason,
        professional_only=professional_only,
    )


def _instruction_actions(assessment: MergedGarmentAssessment) -> list[CareAction]:
    label = assessment.label_extraction
    if label is None:
        return [
            _action("water_wash", Permission.UNKNOWN, reason="care.label_required"),
            _action("domestic_detergent", Permission.PROHIBITED, reason="care.no_water_authority"),
            _action("professional_dry_clean", Permission.UNKNOWN, reason="care.label_required"),
            _action("tumble_dry", Permission.UNKNOWN, reason="care.label_required"),
            _action("iron", Permission.UNKNOWN, reason="care.label_required"),
        ]

    actions: list[CareAction] = []
    if label.wash is not None:
        actions.append(
            _action(
                "water_wash",
                label.wash.permission,
                reason="care.label.wash",
                maximum_temperature_c=label.wash.maximum_temperature_c,
                process=label.wash.process.value,
            )
        )
        detergent_permission = (
            Permission.ALLOWED
            if label.wash.permission in {Permission.ALLOWED, Permission.RESTRICTED}
            else Permission.PROHIBITED
            if label.wash.permission is Permission.PROHIBITED
            else Permission.UNKNOWN
        )
        actions.append(
            _action("domestic_detergent", detergent_permission, reason="care.detergent.wash")
        )
    else:
        actions.extend(
            [
                _action("water_wash", Permission.UNKNOWN, reason="care.label.wash_unknown"),
                _action(
                    "domestic_detergent", Permission.PROHIBITED, reason="care.no_water_authority"
                ),
            ]
        )

    for code, instruction, temperature, process, professional_only in (
        (
            "bleach",
            label.bleach,
            None,
            label.bleach.allowed_type.value if label.bleach else None,
            False,
        ),
        (
            "tumble_dry",
            label.tumble_dry,
            None,
            label.tumble_dry.heat.value if label.tumble_dry else None,
            False,
        ),
        (
            "natural_dry",
            label.natural_drying,
            None,
            ",".join(method.value for method in label.natural_drying.methods)
            if label.natural_drying
            else None,
            False,
        ),
        (
            "iron",
            label.ironing,
            label.ironing.maximum_temperature_c if label.ironing else None,
            label.ironing.steam.value if label.ironing else None,
            False,
        ),
        (
            "professional_dry_clean",
            label.dry_clean,
            None,
            label.dry_clean.process_letter if label.dry_clean else None,
            True,
        ),
        (
            "professional_wet_clean",
            label.professional_wet_clean,
            None,
            label.professional_wet_clean.process_letter if label.professional_wet_clean else None,
            True,
        ),
    ):
        if instruction is not None:
            actions.append(
                _action(
                    code,
                    instruction.permission,
                    reason=f"care.label.{code}",
                    maximum_temperature_c=temperature,
                    process=process,
                    professional_only=professional_only,
                )
            )
        else:
            actions.append(_action(code, Permission.UNKNOWN, reason=f"care.label.{code}_unknown"))
    return actions


def derive_safety_envelope(
    assessment: MergedGarmentAssessment, *, policy_version: str = CARE_POLICY_VERSION
) -> CarePolicy:
    """Derive a conservative policy; unknown evidence never becomes permission."""
    _POLICY_REGISTRY.document(policy_version)
    actions = _instruction_actions(assessment)
    warnings: list[str] = []
    outcome = ValidationOutcome.PASSED

    if assessment.label_extraction is None:
        outcome = ValidationOutcome.NEEDS_BETTER_IMAGE
        warnings.append("CARE_LABEL_REQUIRED")
    if any(conflict.severity is ConflictSeverity.SAFETY for conflict in assessment.conflicts):
        outcome = ValidationOutcome.NEEDS_REVIEW
        warnings.append("SAFETY_EVIDENCE_CONFLICT")
    materials = assessment.label_extraction.materials if assessment.label_extraction else ()
    sensitive = {"leather", "suede", "fur"}
    if any(material.material.lower() in sensitive for material in materials):
        outcome = ValidationOutcome.NEEDS_REVIEW
        warnings.append("SENSITIVE_MATERIAL_REQUIRES_REVIEW")
    if assessment.uncertainties and outcome is ValidationOutcome.PASSED:
        outcome = ValidationOutcome.PASSED_WITH_WARNINGS

    allowed = tuple(
        action
        for action in actions
        if action.permission in {Permission.ALLOWED, Permission.RESTRICTED}
    )
    prohibited = tuple(action for action in actions if action.permission is Permission.PROHIBITED)
    unknown = tuple(action for action in actions if action.permission is Permission.UNKNOWN)
    professional = tuple(action for action in allowed if action.professional_only)
    return CarePolicy(
        care_policy_version=policy_version,
        policy_checksum=_POLICY_REGISTRY.checksum(policy_version),
        outcome=outcome,
        allowed_actions=allowed,
        prohibited_actions=prohibited,
        unknown_actions=unknown,
        professional_only_actions=professional,
        warnings=tuple(dict.fromkeys(warnings)),
        conflicts=assessment.conflicts,
    )


def resolve_practical_preference(
    policy: CarePolicy,
    history: tuple[GarmentServiceEvent, ...],
    *,
    user_preference_action_codes: tuple[str, ...] = (),
) -> CareRecommendation:
    """Select preferences only from currently permitted actions."""
    allowed_codes = {action.code for action in policy.allowed_actions}
    successful = successful_history(history)
    damaging = damaging_history(history)
    history_actions = tuple(event for event in successful if event.method in allowed_codes)
    selected = tuple(dict.fromkeys(event.method for event in history_actions))
    source = "verified_successful_history" if selected else "generic_policy"
    if not selected:
        preferred = tuple(code for code in user_preference_action_codes if code in allowed_codes)
        if preferred:
            selected, source = preferred, "user_confirmed_preference"
        else:
            selected = tuple(
                action.code for action in policy.allowed_actions if not action.professional_only
            )
    explanation = [f"care.recommendation.{source}"]
    if damaging:
        explanation.append("care.history.damaging_event_warning")
    return CareRecommendation(
        recommendation_id=uuid4(),
        selected_action_codes=selected,
        history_event_ids=tuple(event.event_id for event in history_actions),
        preference_source=source,
        explanation_keys=tuple(explanation),
    )


def validate_candidate_claims(
    policy: CarePolicy, claims: tuple[CandidateClaim, ...]
) -> ClaimValidationReport:
    """Gate optional claims without replacing or editing their text."""
    accepted: list[UUID] = []
    blocked: list[UUID] = []
    violations: list[str] = []
    for claim in claims:
        action = policy.action(claim.action_code)
        normalized_text = claim.text.lower()
        if claim.consumer_facing and "solvent" in normalized_text:
            blocked.append(claim.claim_id)
            violations.append("NO_CONSUMER_PROFESSIONAL_SOLVENTS")
        elif action is None or action.permission in {Permission.UNKNOWN, Permission.PROHIBITED}:
            blocked.append(claim.claim_id)
            violations.append(f"ACTION_NOT_AUTHORIZED:{claim.action_code}")
        elif (
            action.maximum_temperature_c is not None
            and claim.maximum_temperature_c is not None
            and claim.maximum_temperature_c > action.maximum_temperature_c
        ):
            blocked.append(claim.claim_id)
            violations.append(f"TEMPERATURE_EXCEEDS_POLICY:{claim.action_code}")
        elif action.professional_only and claim.consumer_facing:
            blocked.append(claim.claim_id)
            violations.append(f"PROFESSIONAL_ONLY_ACTION:{claim.action_code}")
        else:
            accepted.append(claim.claim_id)
    if blocked:
        outcome = ValidationOutcome.BLOCKED
    elif policy.outcome in {ValidationOutcome.NEEDS_BETTER_IMAGE, ValidationOutcome.NEEDS_REVIEW}:
        outcome = policy.outcome
    elif policy.outcome is ValidationOutcome.PASSED_WITH_WARNINGS:
        outcome = ValidationOutcome.PASSED_WITH_WARNINGS
    else:
        outcome = ValidationOutcome.PASSED
    return ClaimValidationReport(
        outcome=outcome,
        accepted_claim_ids=tuple(accepted),
        blocked_claim_ids=tuple(blocked),
        violations=tuple(violations),
        policy_version=policy.care_policy_version,
    )
