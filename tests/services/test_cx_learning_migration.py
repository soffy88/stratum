from scripts.audit_cx_learning_migration import AuditReport, REQUIRED_COLUMNS, ROLLBACK_SQL


def test_cx_learning_migration_is_explicitly_multi_user_but_nullable_for_legacy_rows():
    assert REQUIRED_COLUMNS == {
        ("learning_profile", "user_id"),
        ("learning_plan", "user_id"),
        ("learning_progress", "user_id"),
        ("learning_stuck", "user_id"),
    }
    assert "learning_user_map" in ROLLBACK_SQL
    assert "DROP COLUMN IF EXISTS user_id" in ROLLBACK_SQL


def test_audit_report_does_not_call_unmapped_legacy_rows_ready_for_mapping():
    report = AuditReport(
        schema_present=True,
        missing_columns=(),
        profile_rows=4,
        mapped_profiles=1,
        unmapped_profiles=3,
        child_rows=8,
        mapped_child_rows=2,
        unmapped_child_rows=6,
    )
    assert report.ready_for_mapping is True
    assert report.unmapped_profiles == 3
    assert report.unmapped_child_rows == 6


def test_audit_report_rejects_a_partial_migration_without_mapping_ledger():
    report = AuditReport(
        schema_present=True,
        missing_columns=(),
        missing_tables=("learning_user_map",),
    )
    assert report.ready_for_mapping is False
