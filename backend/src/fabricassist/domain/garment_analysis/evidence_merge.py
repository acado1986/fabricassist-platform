"""Pure, field-authority evidence merger that preserves contradictory facts."""

from __future__ import annotations

from collections import defaultdict

from fabricassist.domain.garment_analysis.conflicts import build_conflict
from fabricassist.domain.garment_analysis.models import (
    ConflictSeverity,
    EvidenceSourceKind,
    FactCandidate,
    MergedGarmentAssessment,
    SelectedFact,
)


def _authority(candidate: FactCandidate, *, safety: bool) -> tuple[int, int]:
    source = candidate.evidence.source_kind
    if safety:
        if (
            source is EvidenceSourceKind.PHOTOGRAPHED_LABEL
            and candidate.explicit_written_instruction
        ):
            rank = 60
        elif source is EvidenceSourceKind.PHOTOGRAPHED_LABEL:
            rank = 50
        elif source is EvidenceSourceKind.VERIFIED_LOOKUP and candidate.exact_variant_match:
            rank = 40
        else:
            rank = 10
        # A photographed prohibition wins against equal or weaker source authority.
        prohibited = int(candidate.value == "prohibited")
        return rank, prohibited
    ranks = {
        EvidenceSourceKind.PHOTOGRAPHED_LABEL: 60,
        EvidenceSourceKind.VERIFIED_LOOKUP: 50 if candidate.exact_variant_match else 30,
        EvidenceSourceKind.HUMAN_CORRECTION: 40,
        EvidenceSourceKind.USER_STATEMENT: 35,
        EvidenceSourceKind.CLEANING_HISTORY: 25,
        EvidenceSourceKind.VISUAL_INFERENCE: 10,
    }
    return ranks[source], 0


def _is_safety_field(field_path: str) -> bool:
    return field_path.startswith(("care.", "wash", "bleach", "tumble", "iron", "dry_clean"))


class EvidenceMerger:
    """Select values by source authority without treating absence as permission."""

    def merge(self, assessment: MergedGarmentAssessment) -> MergedGarmentAssessment:
        grouped: dict[str, list[FactCandidate]] = defaultdict(list)
        for candidate in assessment.source_observations:
            grouped[candidate.field_path].append(candidate)

        selected: list[SelectedFact] = []
        conflicts = list(assessment.conflicts)
        uncertainties = list(assessment.uncertainties)
        for field_path, candidates in grouped.items():
            safety = _is_safety_field(field_path)
            ordered = sorted(
                candidates,
                key=lambda candidate: (
                    *_authority(candidate, safety=safety),
                    candidate.evidence.confidence,
                ),
                reverse=True,
            )
            winner = ordered[0]
            selected.append(
                SelectedFact(
                    field_path=field_path,
                    value=winner.value,
                    selected_evidence=winner.evidence,
                )
            )
            values = {repr(candidate.value) for candidate in candidates}
            if len(values) > 1:
                conflict = build_conflict(
                    field_path=field_path,
                    candidates=tuple(candidates),
                    selected_value=winner.value,
                    resolution_code="SAFETY_AUTHORITY" if safety else "FACTUAL_AUTHORITY",
                )
                conflicts.append(conflict)
                if conflict.severity is ConflictSeverity.SAFETY:
                    uncertainties.append(f"conflict:{field_path}")
        return assessment.model_copy(
            update={
                "selected_facts": tuple(selected),
                "conflicts": tuple(conflicts),
                "uncertainties": tuple(dict.fromkeys(uncertainties)),
            }
        )
