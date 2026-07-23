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
        "evidence_cache_entries",
        "canonical_plan_cache_entries",
        "rendered_answer_cache_entries",
        "review_cases",
        "evidence_corrections",
        "customer_feedback",
        "deletion_requests",
        "object_deletion_outbox",
        "audit_events",
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
        "evidence_cache_entries",
        "canonical_plan_cache_entries",
        "rendered_answer_cache_entries",
        "review_cases",
        "evidence_corrections",
        "customer_feedback",
        "deletion_requests",
        "object_deletion_outbox",
        "audit_events",
    ):
        assert "tenant_id" in Base.metadata.tables[name].c
