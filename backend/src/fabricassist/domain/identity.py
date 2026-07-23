"""Physical-garment identity and service-history value types.

Identity candidates deliberately distinguish product similarity from a verified
physical instance. Only an exact instance identifier may be auto-linked.
"""

from __future__ import annotations

from enum import StrEnum


def normalize_instance_identifier(value: str) -> str:
    """Return the canonical form used for verified instance identifiers."""
    return "".join(value.strip().upper().split())


class IdentityClassification(StrEnum):
    EXACT_INSTANCE = "exact_instance"
    PROBABLE_INSTANCE = "probable_instance"
    SAME_PRODUCT = "same_product"
    VISUAL_CANDIDATE = "visual_candidate"
    NEW_GARMENT = "new_garment"
    IDENTITY_CONFLICT = "identity_conflict"

    @property
    def may_auto_link(self) -> bool:
        """Whether the classification is sufficient to link a physical garment."""
        return self is IdentityClassification.EXACT_INSTANCE

    @property
    def requires_confirmation(self) -> bool:
        return self in {
            IdentityClassification.PROBABLE_INSTANCE,
            IdentityClassification.SAME_PRODUCT,
            IdentityClassification.VISUAL_CANDIDATE,
        }


class GarmentIdentifierType(StrEnum):
    FABRICASSIST_SERIAL = "fabricassist_serial"


def classify_identifier_match(
    *, identifier_found: bool, owner_matches: bool
) -> IdentityClassification:
    """Classify an identifier lookup without ever leaking a foreign garment."""
    if not identifier_found:
        return IdentityClassification.NEW_GARMENT
    if owner_matches:
        return IdentityClassification.EXACT_INSTANCE
    return IdentityClassification.IDENTITY_CONFLICT


class ServiceEventKind(StrEnum):
    PLANNED = "planned"
    PERFORMED = "performed"
    COMPLETED = "completed"

    @property
    def confirms_cleaning(self) -> bool:
        """Only a user-confirmed completed service may state cleaned-before."""
        return self is ServiceEventKind.COMPLETED
