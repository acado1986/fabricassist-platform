from fabricassist.domain.identity import (
    IdentityClassification,
    ServiceEventKind,
    classify_identifier_match,
    normalize_instance_identifier,
)


def test_only_exact_instance_may_auto_link() -> None:
    assert IdentityClassification.EXACT_INSTANCE.may_auto_link
    assert not IdentityClassification.SAME_PRODUCT.may_auto_link
    assert not IdentityClassification.VISUAL_CANDIDATE.may_auto_link


def test_non_exact_candidates_require_confirmation() -> None:
    assert IdentityClassification.PROBABLE_INSTANCE.requires_confirmation
    assert IdentityClassification.SAME_PRODUCT.requires_confirmation
    assert IdentityClassification.VISUAL_CANDIDATE.requires_confirmation
    assert not IdentityClassification.IDENTITY_CONFLICT.requires_confirmation


def test_only_completed_service_confirms_cleaned_before() -> None:
    assert ServiceEventKind.COMPLETED.confirms_cleaning
    assert not ServiceEventKind.PLANNED.confirms_cleaning
    assert not ServiceEventKind.PERFORMED.confirms_cleaning


def test_verified_identifier_normalization_and_ownership_are_required_for_exact_link() -> None:
    assert normalize_instance_identifier(" fa- 123 ") == "FA-123"
    assert (
        classify_identifier_match(identifier_found=True, owner_matches=True)
        is IdentityClassification.EXACT_INSTANCE
    )
    assert (
        classify_identifier_match(identifier_found=True, owner_matches=False)
        is IdentityClassification.IDENTITY_CONFLICT
    )
    assert (
        classify_identifier_match(identifier_found=False, owner_matches=False)
        is IdentityClassification.NEW_GARMENT
    )
