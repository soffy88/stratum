import json
import sys
from pathlib import Path

import scripts.check_pg_acceptance as pg_acceptance
from scripts.check_pg_acceptance import (
    REQUIRED_COLUMNS,
    REQUIRED_HTTP_PATHS,
    REQUIRED_MIGRATIONS,
    REQUIRED_TABLES,
    CatalogResult,
    REQUIRED_MIGRATION_MARKERS,
    migration_contract_errors,
    missing_migration_files,
    catalog_report,
)


def test_pg_acceptance_contract_lists_current_release_surface():
    assert {
        "019_fsrs_evidence.sql",
        "020_knowledge_graph_unification.sql",
        "021_usage_credits.sql",
        "022_personal_model.sql",
        "023_learning_events.sql",
        "024_content_highlight_compat.sql",
        "025_source_fragment_metadata.sql",
        "026_personal_model_import_ledger.sql",
        "027_legacy_knowledge_merge_ledger.sql",
        "028_usage_credit_events.sql",
    } == REQUIRED_MIGRATIONS
    assert "learning_events" in REQUIRED_TABLES
    assert "substrate_chunk" in REQUIRED_TABLES
    assert ("substrates", "license") in REQUIRED_COLUMNS
    assert ("substrate_chunk", "anchor_json") in REQUIRED_COLUMNS
    assert "personal_model_import_ledger" in REQUIRED_TABLES
    assert "legacy_knowledge_merge_ledger" in REQUIRED_TABLES
    assert "usage_credit_events" in REQUIRED_TABLES
    assert ("legacy_knowledge_merge_ledger", "payload_hash") in REQUIRED_COLUMNS
    assert ("usage_credit_events", "status") in REQUIRED_COLUMNS
    assert ("usage_credit_events", "credits") in REQUIRED_COLUMNS
    assert "/api/v1/interactions/content/{content_id}/actions" in REQUIRED_HTTP_PATHS


def test_catalog_result_only_passes_when_everything_is_present():
    result = CatalogResult(set(), set(), set(), True)
    assert result.ok is True
    assert CatalogResult({"024_content_highlight_compat.sql"}, set(), set(), True).ok is False
    assert CatalogResult(set(), {"learning_events"}, set(), True).ok is False
    assert CatalogResult(set(), set(), {("highlights", "content_id")}, True).ok is False
    assert CatalogResult(set(), set(), set(), False).ok is False
    assert CatalogResult(set(), set(), set(), True, False).ok is False
    assert CatalogResult(set(), set(), set(), True, True, False).ok is False
    assert CatalogResult(set(), set(), set(), True, True, True, False).ok is False


def test_catalog_report_is_machine_readable_and_includes_trigger_states():
    report = catalog_report(CatalogResult(set(), set(), set(), True, True, True, False))

    assert report["ok"] is False
    assert report["missing_columns"] == []
    assert report["triggers"]["usage_credit_events_append_only"] is False


def test_acceptance_report_records_offline_pass_before_database_block(tmp_path: Path, monkeypatch):
    report_path = tmp_path / "pg-acceptance.json"

    def unavailable_connection():
        raise RuntimeError("postgres unavailable")

    monkeypatch.setattr(pg_acceptance, "_connect", unavailable_connection)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_pg_acceptance.py",
            "--allow-unavailable",
            "--report-out",
            str(report_path),
        ],
    )

    assert pg_acceptance.main() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert report["migration_files"]["status"] == "passed"
    assert report["database"]["status"] == "blocked"


def test_offline_migration_file_check_detects_missing_and_empty_files(tmp_path: Path):
    (tmp_path / "019_fsrs_evidence.sql").write_text("-- ok\n", encoding="utf-8")
    (tmp_path / "020_knowledge_graph_unification.sql").write_text("", encoding="utf-8")

    missing = missing_migration_files(tmp_path)

    assert "020_knowledge_graph_unification.sql" in missing
    assert "021_usage_credits.sql" in missing
    assert "019_fsrs_evidence.sql" not in missing


def test_offline_migration_contract_check_detects_missing_key_markers(tmp_path: Path):
    for filename, markers in REQUIRED_MIGRATION_MARKERS.items():
        (tmp_path / filename).write_text("\n".join(markers), encoding="utf-8")
    assert migration_contract_errors(tmp_path) == []

    broken = "020_knowledge_graph_unification.sql"
    (tmp_path / broken).write_text("stratum.evidence\n", encoding="utf-8")
    errors = migration_contract_errors(tmp_path)
    assert any("knowledge_claims" in error for error in errors)


def test_usage_credit_event_migration_requires_insert_guard():
    migration = Path("src/stratum/db/pg_migrations/028_usage_credit_events.sql")
    text = migration.read_text(encoding="utf-8")
    assert "TG_OP = 'INSERT'" in text
    assert "NEW.status <> 'pending'" in text
    assert "BEFORE INSERT OR UPDATE OR DELETE" in text
