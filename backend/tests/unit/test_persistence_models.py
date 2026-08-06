from fabricassist.infrastructure.persistence.models import Base


def test_breaking_core_tables_are_registered() -> None:
    assert {
        "garments",
        "analysis_revisions",
        "analysis_revision_images",
        "analysis_branch_results",
        "behavior_versions",
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
        "analysis_branch_results",
        "behavior_versions",
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


def test_garment_analysis_branch_state_constraints_and_versioned_model_runs() -> None:
    branch = Base.metadata.tables["analysis_branch_results"]
    constraints = {constraint.name for constraint in branch.constraints}
    assert {
        "uq_analysis_branch_revision_name",
        "ck_analysis_branch_results_name",
        "ck_analysis_branch_results_status",
        "ck_analysis_branch_results_attempt_count",
        "ck_analysis_branch_results_lease_state",
        "ck_analysis_branch_results_completed_payload",
    } <= constraints
    assert {
        "tenant_id",
        "analysis_revision_id",
        "claim_token",
        "lease_expires_at",
        "result_payload",
    } <= set(branch.c.keys())

    revision = Base.metadata.tables["analysis_revisions"]
    assert {
        "module_version",
        "workflow_version",
        "merged_schema_version",
        "care_policy_version",
        "confidence_policy_version",
        "retry_policy_version",
        "effective_feature_flags",
        "finalized_at",
    } <= set(revision.c.keys())

    model_run = Base.metadata.tables["model_runs"]
    assert {
        "analysis_revision_id",
        "analysis_branch_result_id",
        "retry_number",
        "image_count",
        "role_counts",
        "total_tokens",
        "cached_tokens",
        "thought_tokens",
        "tool_tokens",
        "response_model_version",
        "completed_at",
    } <= set(model_run.c.keys())
