"""Transform retained results into the sole v2 projection and drain old work.

Revision ID: 20260803_0029
Revises: 20260803_0028
"""

from alembic import op

revision = "20260803_0029"
down_revision = "20260803_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A completed v1 result has no safe field-for-field source mapping to the
    # strict v2 dossier. Preserve its immutable audit rows but make the current
    # reader explicitly review-only rather than deserializing old JSON at runtime.
    op.execute(
        """
        UPDATE care_results AS result
        SET status = 'needs_review',
            canonical_data = jsonb_build_object(
                'garment_analysis_result', jsonb_build_object(
                    'schema_version', 'fabricassist-analysis-result-v2',
                    'assessment', jsonb_build_object(
                        'schema_version', 'merged-garment-assessment-v2',
                        'revision_id', result.analysis_revision_id::text,
                        'uncertainties', jsonb_build_array('historical_result_unavailable')
                    ),
                    'care_policy', jsonb_build_object(
                        'care_policy_version', 'historical-unavailable-v1',
                        'policy_checksum', 'unavailable',
                        'outcome', 'needs_review',
                        'warnings', jsonb_build_array('historical_result_unavailable')
                    ),
                    'recommendation', jsonb_build_object(
                        'recommendation_id', result.id::text,
                        'preference_source', 'historical_unavailable'
                    ),
                    'versions', jsonb_build_object(
                        'source_schema', 'legacy-retained-v1',
                        'projection', 'garment-analysis-v2'
                    )
                )
            )
        WHERE NOT (result.canonical_data ? 'garment_analysis_result')
        """
    )
    # Old jobs cannot be resumed with a different executor. Their durable run
    # and scan state records why a fresh v2 analysis is required.
    op.execute(
        """
        UPDATE analysis_job_operations
        SET status = 'obsolete', completed_at = CURRENT_TIMESTAMP, lease_expires_at = NULL
        WHERE status IN ('queued', 'processing')
          AND revision_id NOT IN (SELECT id FROM analysis_revisions)
        """
    )
    op.execute(
        """
        UPDATE ai_runs
        SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP, error_code = 'CUTOVER_CANCELLED'
        WHERE operation = 'scan_analysis' AND status IN ('pending', 'running')
        """
    )


def downgrade() -> None:
    # The v2 projection intentionally has no legacy runtime reader. Development
    # downgrade preserves transformed audit data; production rollback uses backup
    # restore or a forward-compatible binary as documented in the cutover runbook.
    pass
