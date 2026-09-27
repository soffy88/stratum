#!/usr/bin/env python3
"""Validate the deployed PostgreSQL contract required by the current release.

This is intentionally a deployment check, not a substitute for real data or
user-journey testing.  It fails when PostgreSQL is unavailable unless
``--allow-unavailable`` is explicitly supplied for local diagnostics.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from stratum.db.run_pg_migrations import _connect

REQUIRED_MIGRATIONS = {
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
}
REQUIRED_TABLES = {
    "evidence",
    "knowledge_claims",
    "claim_evidence",
    "concept_relations",
    "usage_credits",
    "personal_states",
    "beliefs",
    "context_links",
    "learning_events",
    "highlights",
    "substrate_chunk",
    "personal_model_import_ledger",
    "legacy_knowledge_merge_ledger",
    "usage_credit_events",
}
REQUIRED_COLUMNS = {
    ("highlights", "content_id"),
    ("substrates", "license"),
    ("substrate_chunk", "version"),
    ("substrate_chunk", "anchor_json"),
    ("substrate_chunk", "parser_version"),
    ("personal_model_import_ledger", "payload_hash"),
    ("legacy_knowledge_merge_ledger", "payload_hash"),
    ("usage_credit_events", "idempotency_key"),
    ("usage_credit_events", "status"),
    ("usage_credit_events", "units"),
    ("usage_credit_events", "credits"),
}
REQUIRED_HTTP_PATHS = {
    "/graph/ppr",
    "/api/v1/personal-model/events",
    "/api/v1/interactions/content/{content_id}/actions",
}
DEFAULT_MIGRATION_DIR = Path(__file__).resolve().parents[1] / "src/stratum/db/pg_migrations"
REQUIRED_MIGRATION_MARKERS = {
    "019_fsrs_evidence.sql": (
        "stratum.flashcards",
        "stratum.learning_preferences",
        "stratum.highlights",
    ),
    "020_knowledge_graph_unification.sql": (
        "stratum.evidence",
        "stratum.knowledge_claims",
        "stratum.claim_evidence",
        "stratum.concept_relations",
    ),
    "021_usage_credits.sql": ("stratum.usage_credits",),
    "022_personal_model.sql": (
        "stratum.personal_states",
        "stratum.beliefs",
        "stratum.context_links",
    ),
    "023_learning_events.sql": ("stratum.learning_events", "learning_events_append_only"),
    "024_content_highlight_compat.sql": ("content_id",),
    "025_source_fragment_metadata.sql": (
        "stratum.substrates",
        "stratum.substrate_chunk",
        "anchor_json",
        "parser_version",
    ),
    "026_personal_model_import_ledger.sql": (
        "personal_model_import_ledger",
        "personal_model_import_ledger_append_only",
    ),
    "027_legacy_knowledge_merge_ledger.sql": (
        "legacy_knowledge_merge_ledger",
        "legacy_knowledge_merge_append_only",
    ),
    "028_usage_credit_events.sql": (
        "stratum.usage_credit_events",
        "idempotency_key",
        "status",
        "TG_OP = 'INSERT'",
        "BEFORE INSERT OR UPDATE OR DELETE",
        "usage_credit_events_append_only",
    ),
}


def missing_migration_files(directory: Path = DEFAULT_MIGRATION_DIR) -> set[str]:
    """Return required migration filenames missing or empty on disk."""
    return {
        filename
        for filename in REQUIRED_MIGRATIONS
        if not (directory / filename).is_file() or (directory / filename).stat().st_size == 0
    }


def migration_contract_errors(directory: Path = DEFAULT_MIGRATION_DIR) -> list[str]:
    """Check that each required migration contains its key DDL identifiers."""
    errors: list[str] = []
    for filename, markers in REQUIRED_MIGRATION_MARKERS.items():
        path = directory / filename
        if not path.is_file() or path.stat().st_size == 0:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for marker in markers:
            if marker.lower() not in text:
                errors.append(f"{filename} is missing migration marker: {marker}")
    return errors


def catalog_report(result: "CatalogResult") -> dict[str, object]:
    """Serialize catalog acceptance details for CI artifacts."""
    return {
        "missing_migrations": sorted(result.missing_migrations),
        "missing_tables": sorted(result.missing_tables),
        "missing_columns": sorted(f"{table}.{column}" for table, column in result.missing_columns),
        "triggers": {
            "learning_events_append_only": result.append_only_trigger,
            "personal_model_import_ledger_append_only": result.import_ledger_append_only_trigger,
            "legacy_knowledge_merge_append_only": result.merge_ledger_append_only_trigger,
            "usage_credit_events_append_only": result.usage_credit_event_append_only_trigger,
        },
        "ok": result.ok,
    }


@dataclass(frozen=True)
class CatalogResult:
    missing_migrations: set[str]
    missing_tables: set[str]
    missing_columns: set[tuple[str, str]]
    append_only_trigger: bool
    import_ledger_append_only_trigger: bool = True
    merge_ledger_append_only_trigger: bool = True
    usage_credit_event_append_only_trigger: bool = True

    @property
    def ok(self) -> bool:
        return (
            not self.missing_migrations
            and not self.missing_tables
            and not self.missing_columns
            and self.append_only_trigger
            and self.import_ledger_append_only_trigger
            and self.merge_ledger_append_only_trigger
            and self.usage_credit_event_append_only_trigger
        )


def inspect_catalog(conn) -> CatalogResult:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM public._pg_migrations")
        applied = {row[0] for row in cur.fetchall()}
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'stratum' AND table_name = ANY(%s)",
            (list(REQUIRED_TABLES),),
        )
        tables = {row[0] for row in cur.fetchall()}
        values = ", ".join(["(%s, %s)"] * len(REQUIRED_COLUMNS))
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'stratum' AND (table_name, column_name) IN "
            f"(VALUES {values})",
            tuple(value for pair in sorted(REQUIRED_COLUMNS) for value in pair),
        )
        columns = {(row[0], row[1]) for row in cur.fetchall()}
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgrelid = to_regclass(%s) AND tgname = %s)",
            ("stratum.learning_events", "learning_events_append_only"),
        )
        trigger = bool(cur.fetchone()[0])
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgrelid = to_regclass(%s) "
            "AND tgname = %s)",
            ("stratum.personal_model_import_ledger", "personal_model_import_ledger_append_only"),
        )
        import_ledger_trigger = bool(cur.fetchone()[0])
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgrelid = to_regclass(%s) "
            "AND tgname = %s)",
            ("stratum.legacy_knowledge_merge_ledger", "legacy_knowledge_merge_append_only"),
        )
        merge_ledger_trigger = bool(cur.fetchone()[0])
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgrelid = to_regclass(%s) "
            "AND tgname = %s)",
            ("stratum.usage_credit_events", "usage_credit_events_append_only"),
        )
        usage_credit_event_trigger = bool(cur.fetchone()[0])
    return CatalogResult(
        REQUIRED_MIGRATIONS - applied,
        REQUIRED_TABLES - tables,
        REQUIRED_COLUMNS - columns,
        trigger,
        import_ledger_trigger,
        merge_ledger_trigger,
        usage_credit_event_trigger,
    )


def inspect_openapi(base_url: str) -> set[str]:
    url = base_url.rstrip("/") + "/openapi.json"
    with urlopen(url, timeout=10) as response:  # noqa: S310 - operator-supplied deployment URL
        document = json.load(response)
    return REQUIRED_HTTP_PATHS - set(document.get("paths", {}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-base-url", help="Optional deployed API base URL")
    parser.add_argument(
        "--migration-dir",
        type=Path,
        default=DEFAULT_MIGRATION_DIR,
        help="Migration directory for the offline file check",
    )
    parser.add_argument(
        "--report-out", type=Path, help="Optional machine-readable acceptance report"
    )
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="Report a blocked local environment as exit 0 (never use in release CI)",
    )
    args = parser.parse_args()
    report: dict[str, object] = {
        "schema_version": 1,
        "report_type": "postgres_acceptance",
        "status": "not_checked",
        "migration_files": {
            "status": "not_checked",
            "missing_or_empty": [],
            "contract_errors": [],
        },
        "database": {"status": "not_checked"},
        "http": {"status": "not_requested"},
    }

    def write_report() -> None:
        if args.report_out:
            args.report_out.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    missing_files = missing_migration_files(args.migration_dir)
    report["migration_files"]["missing_or_empty"] = sorted(missing_files)  # type: ignore[index]
    if missing_files:
        report["migration_files"]["status"] = "failed"  # type: ignore[index]
        print(f"missing or empty migration files: {sorted(missing_files)}")
        report["status"] = "failed"
        write_report()
        return 1
    contract_errors = migration_contract_errors(args.migration_dir)
    report["migration_files"]["contract_errors"] = contract_errors  # type: ignore[index]
    if contract_errors:
        report["migration_files"]["status"] = "failed"  # type: ignore[index]
        for error in contract_errors:
            print(error)
        report["status"] = "failed"
        write_report()
        return 1

    report["migration_files"]["status"] = "passed"  # type: ignore[index]

    try:
        conn = _connect()
    except Exception as exc:
        print(f"PG acceptance BLOCKED: cannot connect to PostgreSQL: {type(exc).__name__}: {exc}")
        report["status"] = "blocked"
        report["database"] = {"status": "blocked", "error": f"{type(exc).__name__}: {exc}"}
        write_report()
        return 0 if args.allow_unavailable else 2

    try:
        result = inspect_catalog(conn)
    finally:
        conn.close()
    report["database"] = catalog_report(result) | {"status": "passed" if result.ok else "failed"}

    if result.missing_migrations:
        print(f"missing migrations: {sorted(result.missing_migrations)}")
    if result.missing_tables:
        print(f"missing stratum tables: {sorted(result.missing_tables)}")
    if result.missing_columns:
        print(f"missing stratum columns: {sorted(result.missing_columns)}")
    if not result.append_only_trigger:
        print("missing trigger: stratum.learning_events.learning_events_append_only")
    if not result.import_ledger_append_only_trigger:
        print(
            "missing trigger: "
            "stratum.personal_model_import_ledger.personal_model_import_ledger_append_only"
        )
    if not result.merge_ledger_append_only_trigger:
        print(
            "missing trigger: "
            "stratum.legacy_knowledge_merge_ledger.legacy_knowledge_merge_append_only"
        )
    if not result.usage_credit_event_append_only_trigger:
        print("missing trigger: stratum.usage_credit_events.usage_credit_events_append_only")

    missing_paths: set[str] = set()
    if args.http_base_url:
        try:
            missing_paths = inspect_openapi(args.http_base_url)
        except Exception as exc:
            print(f"HTTP OpenAPI acceptance failed: {exc}")
            report["status"] = "failed"
            report["http"] = {"status": "failed", "error": str(exc)}
            write_report()
            return 1
        report["http"] = {
            "status": "passed" if not missing_paths else "failed",
            "missing_paths": sorted(missing_paths),
        }
        if missing_paths:
            print(f"missing OpenAPI paths: {sorted(missing_paths)}")

    if not result.ok or missing_paths:
        print("PG acceptance FAILED")
        report["status"] = "failed"
        write_report()
        return 1
    print("PG acceptance OK: migrations, canonical tables, trigger, and requested OpenAPI paths")
    report["status"] = "passed"
    write_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
