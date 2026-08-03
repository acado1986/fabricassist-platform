"""Strict, transport-neutral value contracts for garment-analysis v2."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Text = Annotated[str, Field(min_length=1, max_length=5000)]
ShortText = Annotated[str, Field(min_length=1, max_length=120)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceSourceKind(StrEnum):
    PHOTOGRAPHED_LABEL = "photographed_label"
    VISUAL_INFERENCE = "visual_inference"
    USER_STATEMENT = "user_statement"
    VERIFIED_LOOKUP = "verified_lookup"
    HUMAN_CORRECTION = "human_correction"
    CLEANING_HISTORY = "cleaning_history"


class EvidenceCertainty(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"


class Permission(StrEnum):
    ALLOWED = "allowed"
    PROHIBITED = "prohibited"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class ValidationOutcome(StrEnum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    BLOCKED = "blocked"
    NEEDS_BETTER_IMAGE = "needs_better_image"
    NEEDS_REVIEW = "needs_review"


class FieldEvidence(StrictModel):
    field_path: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.\[\]-]{0,159}$")]
    source_kind: EvidenceSourceKind
    source_image_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=8)
    certainty: EvidenceCertainty
    confidence: int = Field(ge=0, le=100)
    original_text: str | None = Field(default=None, max_length=5000)
    uncertainty_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def unknown_evidence_has_reason(self) -> FieldEvidence:
        if self.certainty is EvidenceCertainty.UNKNOWN and not self.uncertainty_reason:
            raise ValueError("unknown evidence requires uncertainty_reason")
        return self


class CauseHypothesis(StrictModel):
    cause: ShortText
    confidence: int = Field(ge=0, le=100)
    source_image_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)


class GarmentIssueKind(StrEnum):
    STAIN = "stain"
    HOLE = "hole"
    TEAR = "tear"
    LOOSE_SEAM = "loose_seam"
    PILLING = "pilling"
    FADING = "fading"
    DISCOLORATION = "discoloration"
    DEFORMATION = "deformation"
    STRETCHING = "stretching"
    MISSING_PART = "missing_part"
    OTHER = "other"


class IssueSeverity(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class GarmentIssue(StrictModel):
    issue_id: UUID
    kind: GarmentIssueKind
    severity: IssueSeverity
    location: str = Field(min_length=1, max_length=300)
    observed_description: Text
    confidence: int = Field(ge=0, le=100)
    source_image_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)
    suspected_causes: tuple[CauseHypothesis, ...] = Field(default_factory=tuple, max_length=8)
    confirmed_cause: str | None = Field(default=None, min_length=1, max_length=300)
    confirmed_cause_source: EvidenceSourceKind | None = None

    @model_validator(mode="after")
    def confirmed_cause_is_not_visual_only(self) -> GarmentIssue:
        if self.confirmed_cause and self.confirmed_cause_source not in {
            EvidenceSourceKind.USER_STATEMENT,
            EvidenceSourceKind.HUMAN_CORRECTION,
            EvidenceSourceKind.VERIFIED_LOOKUP,
        }:
            raise ValueError("confirmed cause needs user, human, or verified evidence")
        if not self.confirmed_cause and self.confirmed_cause_source is not None:
            raise ValueError("confirmed_cause_source requires confirmed_cause")
        return self


class VisualMaterialHypothesis(StrictModel):
    material: ShortText
    confidence: int = Field(ge=0, le=100)
    source_image_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)
    certainty: Literal[EvidenceCertainty.INFERRED] = EvidenceCertainty.INFERRED


class GarmentInspection(StrictModel):
    schema_version: str = "garment-inspection-v2"
    category: str = Field(default="unknown", max_length=120)
    subtype: str | None = Field(default=None, max_length=120)
    colors: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=12)
    pattern: str = Field(default="unknown", max_length=120)
    features: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=30)
    visual_material_hypotheses: tuple[VisualMaterialHypothesis, ...] = Field(
        default_factory=tuple, max_length=12
    )
    issues: tuple[GarmentIssue, ...] = Field(default_factory=tuple, max_length=30)
    overall_condition: str = Field(default="unknown", max_length=120)
    overall_confidence: int = Field(ge=0, le=100)
    uncertain_fields: tuple[str, ...] = Field(default_factory=tuple, max_length=40)
    field_evidence: tuple[FieldEvidence, ...] = Field(default_factory=tuple, max_length=80)


class VisibleLabelText(StrictModel):
    image_id: UUID
    text: str = Field(min_length=1, max_length=5000)
    language: str = Field(min_length=2, max_length=20)
    confidence: int = Field(ge=0, le=100)


class MaterialComposition(StrictModel):
    material: ShortText
    percentage: float | None = Field(default=None, ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    source_image_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)


class WashProcess(StrEnum):
    MACHINE = "machine"
    HAND = "hand"
    GENTLE = "gentle"
    NORMAL = "normal"
    UNKNOWN = "unknown"


class BleachType(StrEnum):
    CHLORINE = "chlorine"
    OXYGEN = "oxygen"
    NON_CHLORINE = "non_chlorine"
    UNKNOWN = "unknown"


class TumbleDryHeat(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class NaturalDryingMethod(StrEnum):
    LINE_DRY = "line_dry"
    DRIP_DRY = "drip_dry"
    DRY_FLAT = "dry_flat"
    SHADE = "shade"
    UNKNOWN = "unknown"


class IronSteam(StrEnum):
    ALLOWED = "allowed"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


class ProfessionalProcessSeverity(StrEnum):
    NORMAL = "normal"
    GENTLE = "gentle"
    UNKNOWN = "unknown"


class CareInstruction(StrictModel):
    permission: Permission
    evidence: FieldEvidence

    @model_validator(mode="after")
    def non_unknown_instruction_requires_evidence(self) -> CareInstruction:
        if (
            self.permission is not Permission.UNKNOWN
            and self.evidence.certainty is EvidenceCertainty.UNKNOWN
        ):
            raise ValueError("known care instruction requires known evidence")
        return self


class WashInstruction(CareInstruction):
    maximum_temperature_c: int | None = Field(default=None, ge=10, le=95)
    process: WashProcess = WashProcess.UNKNOWN

    @model_validator(mode="after")
    def wash_limits_are_compatible(self) -> WashInstruction:
        if self.permission is Permission.PROHIBITED and self.maximum_temperature_c is not None:
            raise ValueError("prohibited wash cannot include a maximum temperature")
        if self.maximum_temperature_c is not None and self.permission is Permission.UNKNOWN:
            raise ValueError("wash temperature requires a known wash permission")
        return self


class BleachInstruction(CareInstruction):
    allowed_type: BleachType = BleachType.UNKNOWN


class TumbleDryInstruction(CareInstruction):
    heat: TumbleDryHeat = TumbleDryHeat.UNKNOWN


class NaturalDryingInstruction(CareInstruction):
    methods: tuple[NaturalDryingMethod, ...] = Field(default_factory=tuple, max_length=4)


class IroningInstruction(CareInstruction):
    maximum_temperature_c: int | None = Field(default=None, ge=80, le=230)
    steam: IronSteam = IronSteam.UNKNOWN


class ProfessionalCareInstruction(CareInstruction):
    process_letter: str | None = Field(default=None, pattern=r"^[A-Z]{1,2}$")
    severity: ProfessionalProcessSeverity = ProfessionalProcessSeverity.UNKNOWN


class LabelExtraction(StrictModel):
    schema_version: str = "label-extraction-v2"
    visible_text: tuple[VisibleLabelText, ...] = Field(default_factory=tuple, max_length=24)
    materials: tuple[MaterialComposition, ...] = Field(default_factory=tuple, max_length=12)
    wash: WashInstruction | None = None
    bleach: BleachInstruction | None = None
    tumble_dry: TumbleDryInstruction | None = None
    natural_drying: NaturalDryingInstruction | None = None
    ironing: IroningInstruction | None = None
    dry_clean: ProfessionalCareInstruction | None = None
    professional_wet_clean: ProfessionalCareInstruction | None = None
    written_warnings: tuple[Text, ...] = Field(default_factory=tuple, max_length=24)
    uncertain_symbols: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=24)
    field_evidence: tuple[FieldEvidence, ...] = Field(default_factory=tuple, max_length=100)
    overall_confidence: int = Field(ge=0, le=100)
    material_percentage_tolerance: float = Field(default=1.0, ge=0, le=5)
    material_percentage_uncertainty: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def record_material_total_uncertainty(self) -> LabelExtraction:
        percentages = [material.percentage for material in self.materials]
        known_percentages = [percentage for percentage in percentages if percentage is not None]
        if (
            len(percentages) > 1
            and len(known_percentages) == len(percentages)
            and abs(sum(known_percentages) - 100) > self.material_percentage_tolerance
            and self.material_percentage_uncertainty is None
        ):
            object.__setattr__(
                self,
                "material_percentage_uncertainty",
                "MATERIAL_PERCENTAGES_DO_NOT_TOTAL_100",
            )
        return self


class CorrectionSource(StrEnum):
    CUSTOMER = "customer"
    OPERATOR = "operator"
    SYSTEM = "system"


class CorrectionConfirmation(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class EvidenceCorrection(StrictModel):
    correction_id: UUID
    revision_id: UUID
    field_path: str = Field(pattern=r"^[a-z][a-z0-9_.\[\]-]{0,159}$")
    previous_value: JsonValue
    corrected_value: JsonValue
    source_image_id: UUID | None = None
    source: CorrectionSource
    reason: str = Field(min_length=1, max_length=500)
    confirmation: CorrectionConfirmation
    supersedes_correction_id: UUID | None = None

    @model_validator(mode="after")
    def safety_correction_requires_review(self) -> EvidenceCorrection:
        safety = self.field_path.startswith(
            ("care.", "wash", "bleach", "tumble", "iron", "dry_clean")
        )
        if (
            safety
            and self.source is CorrectionSource.CUSTOMER
            and self.confirmation is CorrectionConfirmation.ACCEPTED
        ):
            raise ValueError(
                "customer safety corrections require image evidence or operator review"
            )
        return self


class BranchReference(StrictModel):
    branch_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    result_id: UUID
    schema_version: str = Field(min_length=1, max_length=80)


class FactCandidate(StrictModel):
    field_path: str = Field(pattern=r"^[a-z][a-z0-9_.\[\]-]{0,159}$")
    value: JsonValue
    evidence: FieldEvidence
    explicit_written_instruction: bool = False
    exact_variant_match: bool = False


class SelectedFact(StrictModel):
    field_path: str
    value: JsonValue
    selected_evidence: FieldEvidence


class ConflictSeverity(StrEnum):
    WARNING = "warning"
    SAFETY = "safety"


class EvidenceConflict(StrictModel):
    conflict_id: UUID
    field_path: str
    values: tuple[JsonValue, ...] = Field(min_length=2, max_length=8)
    evidence: tuple[FieldEvidence, ...] = Field(min_length=2, max_length=8)
    selected_value: JsonValue | None = None
    resolution_code: ShortText
    explanation_key: ShortText
    severity: ConflictSeverity


class MergedGarmentAssessment(StrictModel):
    schema_version: str = "merged-garment-assessment-v2"
    revision_id: UUID
    branch_references: tuple[BranchReference, ...] = Field(default_factory=tuple, max_length=8)
    garment_inspection: GarmentInspection | None = None
    label_extraction: LabelExtraction | None = None
    selected_facts: tuple[SelectedFact, ...] = Field(default_factory=tuple, max_length=160)
    source_observations: tuple[FactCandidate, ...] = Field(default_factory=tuple, max_length=320)
    conflicts: tuple[EvidenceConflict, ...] = Field(default_factory=tuple, max_length=80)
    uncertainties: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=80)
    prior_exact_garment_confirmed: bool = False


class CareAction(StrictModel):
    code: ShortText
    permission: Permission
    maximum_temperature_c: int | None = Field(default=None, ge=10, le=230)
    process: str | None = Field(default=None, max_length=80)
    evidence_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    reason_key: ShortText
    professional_only: bool = False


class CarePolicy(StrictModel):
    care_policy_version: str
    policy_checksum: str
    outcome: ValidationOutcome
    allowed_actions: tuple[CareAction, ...] = Field(default_factory=tuple, max_length=40)
    prohibited_actions: tuple[CareAction, ...] = Field(default_factory=tuple, max_length=40)
    unknown_actions: tuple[CareAction, ...] = Field(default_factory=tuple, max_length=40)
    professional_only_actions: tuple[CareAction, ...] = Field(default_factory=tuple, max_length=16)
    warnings: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=40)
    conflicts: tuple[EvidenceConflict, ...] = Field(default_factory=tuple, max_length=80)

    def action(self, code: str) -> CareAction | None:
        return next(
            (
                action
                for group in (self.allowed_actions, self.prohibited_actions, self.unknown_actions)
                for action in group
                if action.code == code
            ),
            None,
        )


class CareRecommendation(StrictModel):
    recommendation_id: UUID
    selected_action_codes: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=24)
    history_event_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=16)
    preference_source: str = Field(min_length=1, max_length=80)
    explanation_keys: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=24)


class CandidateClaim(StrictModel):
    claim_id: UUID
    action_code: ShortText
    maximum_temperature_c: int | None = Field(default=None, ge=10, le=230)
    consumer_facing: bool = True
    text: Text


class ClaimValidationReport(StrictModel):
    outcome: ValidationOutcome
    accepted_claim_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=100)
    blocked_claim_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=100)
    violations: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=100)
    policy_version: str


class StainTreatmentStep(StrictModel):
    claim: CandidateClaim
    source_image_ids: tuple[UUID, ...] = Field(min_length=1, max_length=8)
    confidence: int = Field(ge=0, le=100)


class StainTreatment(StrictModel):
    schema_version: str = "stain-treatment-v2"
    treatment_id: UUID
    hypotheses: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=12)
    steps: tuple[StainTreatmentStep, ...] = Field(default_factory=tuple, max_length=20)
    uncertainty: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=24)
    overall_confidence: int = Field(ge=0, le=100)


class ValidatedStainTreatment(StrictModel):
    treatment_id: UUID
    accepted_claim_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=20)
    blocked_claim_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=20)
    conflicts: tuple[EvidenceConflict, ...] = Field(default_factory=tuple, max_length=40)
    outcome: ValidationOutcome
    care_policy_version: str


class FabricAssistAnalysisResult(StrictModel):
    schema_version: str = "fabricassist-analysis-result-v2"
    assessment: MergedGarmentAssessment
    care_policy: CarePolicy
    recommendation: CareRecommendation
    validated_stain_treatment: ValidatedStainTreatment | None = None
    clearer_image_requests: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=20)
    versions: dict[str, str] = Field(default_factory=dict, max_length=24)
    localization_template_inputs: dict[str, JsonValue] = Field(default_factory=dict, max_length=80)
