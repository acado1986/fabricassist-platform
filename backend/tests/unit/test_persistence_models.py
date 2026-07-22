from fabricassist.infrastructure.persistence.models import Base


def test_breaking_core_tables_are_registered() -> None:
    assert {
        "garments",
        "analysis_revisions",
        "analysis_revision_images",
        "garment_evidence_dossiers",
        "proposed_care_plans",
        "care_validation_reports",
        "care_results",
        "rendered_answers",
    } <= set(Base.metadata.tables)
    assert "label_extractions" not in Base.metadata.tables


def test_tenant_owned_core_tables_have_tenant_id() -> None:
    for name in (
        "garments",
        "analysis_revisions",
        "garment_evidence_dossiers",
        "proposed_care_plans",
        "care_validation_reports",
        "care_results",
        "rendered_answers",
    ):
        assert "tenant_id" in Base.metadata.tables[name].c
