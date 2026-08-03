from datetime import UTC, datetime
from uuid import uuid4

from fabricassist.domain.garment_analysis.care_policy import (
    CarePolicyRegistry,
    derive_safety_envelope,
    resolve_practical_preference,
    validate_candidate_claims,
)
from fabricassist.domain.garment_analysis.cleaning_history import (
    CleaningOutcome,
    GarmentServiceEvent,
    ServiceLifecycleKind,
    eligible_history,
)
from fabricassist.domain.garment_analysis.models import (
    CandidateClaim,
    EvidenceCertainty,
    EvidenceSourceKind,
    FieldEvidence,
    GarmentInspection,
    GarmentIssue,
    GarmentIssueKind,
    IssueSeverity,
    LabelExtraction,
    MaterialComposition,
    MergedGarmentAssessment,
    Permission,
    StainTreatment,
    StainTreatmentStep,
    ValidationOutcome,
    WashInstruction,
)
from fabricassist.domain.garment_analysis.stain_policy import (
    is_stain_analysis_eligible,
    validate_stain_treatment,
)


def evidence(field: str) -> FieldEvidence:
    return FieldEvidence(
        field_path=field,
        source_kind=EvidenceSourceKind.PHOTOGRAPHED_LABEL,
        source_image_ids=(uuid4(),),
        certainty=EvidenceCertainty.OBSERVED,
        confidence=99,
    )


def assessment(
    *, wash: Permission | None = None, temperature: int | None = None
) -> MergedGarmentAssessment:
    label = None
    if wash is not None:
        label = LabelExtraction(
            wash=WashInstruction(
                permission=wash,
                maximum_temperature_c=temperature,
                evidence=evidence("care.wash"),
            ),
            overall_confidence=99,
        )
    return MergedGarmentAssessment(revision_id=uuid4(), label_extraction=label)


def event(
    *, exact: bool, lifecycle: ServiceLifecycleKind, outcome: CleaningOutcome, method: str
) -> GarmentServiceEvent:
    return GarmentServiceEvent(
        event_id=uuid4(),
        garment_id=uuid4(),
        exact_garment_confirmed=exact,
        lifecycle_kind=lifecycle,
        outcome=outcome,
        method=method,
        confirmed_by="operator",
        occurred_at=datetime.now(UTC),
        detail_schema_version="service-event-v2",
    )


def test_missing_label_never_authorizes_water_or_detergent() -> None:
    policy = derive_safety_envelope(assessment())
    assert policy.outcome == ValidationOutcome.NEEDS_BETTER_IMAGE
    assert policy.action("water_wash").permission == Permission.UNKNOWN  # type: ignore[union-attr]
    assert policy.action("domestic_detergent").permission == Permission.PROHIBITED  # type: ignore[union-attr]


def test_label_temperature_sets_envelope_and_blocks_over_limit_claim() -> None:
    policy = derive_safety_envelope(assessment(wash=Permission.ALLOWED, temperature=30))
    report = validate_candidate_claims(
        policy,
        (
            CandidateClaim(
                claim_id=uuid4(), action_code="water_wash", maximum_temperature_c=40, text="wash"
            ),
        ),
    )
    assert report.outcome == ValidationOutcome.BLOCKED
    assert report.violations == ("TEMPERATURE_EXCEEDS_POLICY:water_wash",)


def test_successful_history_never_selects_action_outside_current_envelope() -> None:
    policy = derive_safety_envelope(assessment(wash=Permission.PROHIBITED))
    recommendation = resolve_practical_preference(
        policy,
        (
            event(
                exact=True,
                lifecycle=ServiceLifecycleKind.COMPLETED,
                outcome=CleaningOutcome.SUCCESSFUL,
                method="water_wash",
            ),
        ),
    )
    assert "water_wash" not in recommendation.selected_action_codes
    assert recommendation.preference_source == "generic_policy"


def test_history_requires_exact_performed_or_completed_non_superseded_event() -> None:
    records = (
        event(
            exact=False,
            lifecycle=ServiceLifecycleKind.COMPLETED,
            outcome=CleaningOutcome.SUCCESSFUL,
            method="water_wash",
        ),
        event(
            exact=True,
            lifecycle=ServiceLifecycleKind.PLANNED,
            outcome=CleaningOutcome.UNKNOWN,
            method="water_wash",
        ),
        event(
            exact=True,
            lifecycle=ServiceLifecycleKind.PERFORMED,
            outcome=CleaningOutcome.SUCCESSFUL,
            method="water_wash",
        ),
    )
    assert eligible_history(records) == (records[2],)


def test_policy_checksum_is_stable_for_activated_asset() -> None:
    registry = CarePolicyRegistry()
    assert registry.document()["version"] == "care-policy-v2"
    assert registry.checksum() == registry.checksum()


def test_stain_gate_requires_image_issue_policy_and_feature() -> None:
    issue = GarmentIssue(
        issue_id=uuid4(),
        kind=GarmentIssueKind.STAIN,
        severity=IssueSeverity.MINOR,
        location="front",
        observed_description="spot",
        confidence=90,
        source_image_ids=(uuid4(),),
    )
    inspection = GarmentInspection(overall_confidence=90, issues=(issue,))
    policy = derive_safety_envelope(assessment(wash=Permission.ALLOWED, temperature=30))
    assert is_stain_analysis_eligible(
        stain_image_count=1,
        user_requested=False,
        inspection=inspection,
        policy=policy,
        feature_enabled=True,
        reusable_success_exists=False,
    )
    assert not is_stain_analysis_eligible(
        stain_image_count=1,
        user_requested=False,
        inspection=inspection,
        policy=policy,
        feature_enabled=False,
        reusable_success_exists=False,
    )


def test_stain_validation_retains_proposal_but_blocks_consumer_solvent_claim() -> None:
    policy = derive_safety_envelope(assessment(wash=Permission.ALLOWED, temperature=30))
    claim = CandidateClaim(claim_id=uuid4(), action_code="water_wash", text="apply solvent at home")
    treatment = StainTreatment(
        treatment_id=uuid4(),
        steps=(StainTreatmentStep(claim=claim, source_image_ids=(uuid4(),), confidence=70),),
        overall_confidence=70,
    )
    validated = validate_stain_treatment(policy, treatment)
    assert validated.blocked_claim_ids == (claim.claim_id,)
    assert treatment.steps[0].claim.text == "apply solvent at home"


def test_label_prohibition_blocks_domestic_detergent_claim() -> None:
    policy = derive_safety_envelope(assessment(wash=Permission.PROHIBITED))
    report = validate_candidate_claims(
        policy,
        (CandidateClaim(claim_id=uuid4(), action_code="domestic_detergent", text="use detergent"),),
    )
    assert report.outcome == ValidationOutcome.BLOCKED
    assert report.violations == ("ACTION_NOT_AUTHORIZED:domestic_detergent",)


def test_sensitive_confirmed_label_material_forces_review() -> None:
    label = LabelExtraction(
        materials=(
            MaterialComposition(
                material="leather", percentage=100, confidence=99, source_image_ids=(uuid4(),)
            ),
        ),
        overall_confidence=99,
    )
    policy = derive_safety_envelope(
        MergedGarmentAssessment(revision_id=uuid4(), label_extraction=label)
    )
    assert policy.outcome == ValidationOutcome.NEEDS_REVIEW
    assert "SENSITIVE_MATERIAL_REQUIRES_REVIEW" in policy.warnings


def test_finalization_preserves_history_conflicts_but_label_limits_win() -> None:
    from fabricassist.domain.garment_analysis.finalization import finalize_analysis
    from fabricassist.domain.garment_analysis.models import (
        BranchReference,
        TumbleDryInstruction,
    )

    no_tumble = TumbleDryInstruction(
        permission=Permission.PROHIBITED,
        evidence=evidence("care.tumble_dry.permission"),
    )
    label = LabelExtraction(
        wash=WashInstruction(
            permission=Permission.ALLOWED,
            maximum_temperature_c=30,
            evidence=evidence("care.wash"),
        ),
        tumble_dry=no_tumble,
        overall_confidence=99,
    )
    historical = GarmentServiceEvent(
        event_id=uuid4(),
        garment_id=uuid4(),
        exact_garment_confirmed=True,
        lifecycle_kind=ServiceLifecycleKind.COMPLETED,
        outcome=CleaningOutcome.SUCCESSFUL,
        method="water_wash",
        water_temperature_c=40,
        drying_method="tumble_dry",
        confirmed_by="operator",
        occurred_at=datetime.now(UTC),
        detail_schema_version="service-event-v2",
    )
    result = finalize_analysis(
        revision_id=uuid4(),
        branch_references=(
            BranchReference(
                branch_name="label_extraction", result_id=uuid4(), schema_version="label-v2"
            ),
        ),
        garment_inspection=None,
        label_extraction=label,
        history=(historical,),
    )

    selected = {item.field_path: item.value for item in result.assessment.selected_facts}
    assert selected["care.wash.maximum_temperature_c"] == 30
    assert selected["care.tumble_dry.permission"] == "prohibited"
    assert result.care_policy.action("water_wash").maximum_temperature_c == 30  # type: ignore[union-attr]
    assert result.care_policy.action("tumble_dry").permission is Permission.PROHIBITED  # type: ignore[union-attr]
    assert {conflict.field_path for conflict in result.assessment.conflicts} == {
        "care.wash.maximum_temperature_c",
        "care.tumble_dry.permission",
    }


def test_natural_drying_is_a_policy_action() -> None:
    from fabricassist.domain.garment_analysis.models import (
        NaturalDryingInstruction,
        NaturalDryingMethod,
    )

    label = LabelExtraction(
        natural_drying=NaturalDryingInstruction(
            permission=Permission.ALLOWED,
            methods=(NaturalDryingMethod.DRY_FLAT, NaturalDryingMethod.SHADE),
            evidence=evidence("care.natural_drying"),
        ),
        overall_confidence=99,
    )
    policy = derive_safety_envelope(
        MergedGarmentAssessment(revision_id=uuid4(), label_extraction=label)
    )
    action = policy.action("natural_dry")
    assert action is not None
    assert action.permission is Permission.ALLOWED
    assert action.process == "dry_flat,shade"
