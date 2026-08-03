"""Conflict classification helpers for immutable evidence observations."""

from __future__ import annotations

from uuid import uuid4

from pydantic import JsonValue

from fabricassist.domain.garment_analysis.models import (
    ConflictSeverity,
    EvidenceConflict,
    FactCandidate,
)


def conflict_severity(field_path: str) -> ConflictSeverity:
    if field_path.startswith(("care.", "wash", "bleach", "tumble", "iron", "dry_clean")):
        return ConflictSeverity.SAFETY
    return ConflictSeverity.WARNING


def build_conflict(
    *,
    field_path: str,
    candidates: tuple[FactCandidate, ...],
    selected_value: JsonValue | None,
    resolution_code: str,
) -> EvidenceConflict:
    return EvidenceConflict(
        conflict_id=uuid4(),
        field_path=field_path,
        values=tuple(candidate.value for candidate in candidates),
        evidence=tuple(candidate.evidence for candidate in candidates),
        selected_value=selected_value,
        resolution_code=resolution_code,
        explanation_key=f"conflict.{resolution_code.lower()}",
        severity=conflict_severity(field_path),
    )
