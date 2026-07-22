#!/usr/bin/env python3
"""Generate PostgreSQL DDL for the `stratum` schema from the live DuckDB schema dump.

P1.1 of the AII merge (DB convergence). Reads _schema_dump.json (produced by
introspecting the live DuckDB) and emits faithful PG `CREATE TABLE stratum.<t>`
DDL. The `stratum` schema lives alongside AII's `aii` schema in aii-postgres.

Type mapping (DuckDB -> PG):
  VARCHAR        -> TEXT
  VARCHAR[]      -> TEXT[]
  JSON           -> JSONB
  TIMESTAMP      -> TIMESTAMPTZ
  FLOAT[1024]    -> vector(1024)   (pgvector; matches AII / BGE-M3)
  FLOAT/DOUBLE   -> DOUBLE PRECISION
  BIGINT/INTEGER/BOOLEAN/DATE -> same

Search columns (tsvector / substrate embeddings) are added later in P1.4, not here.
Legacy pre-merge duplicate tables are skipped.

DEFAULT / UNIQUE recovery (added after a 2026-07 incident: every table this
script generated was missing DEFAULT values and UNIQUE constraints, because
_schema_dump.json only records col/type/null — nothing else — so app code
that relies on the DB filling in a default on INSERT got silent NULLs instead,
surfacing as a 500 the first time someone hit a code path that omitted an
"optional" column. _schema_dump.json can't be fixed retroactively (it's a
frozen snapshot), so this cross-references the *original* DuckDB migration
SQL in src/stratum/db/migrations/*.sql — the authoritative source those
columns' DEFAULT/UNIQUE declarations came from — and merges them in. Best-
effort regex parsing (CREATE TABLE inline DEFAULT/UNIQUE, standalone ALTER
TABLE ... SET DEFAULT, and CREATE UNIQUE INDEX), not a full SQL grammar — good
enough for the patterns this migration set actually uses. Verify the output
against a real table if you add a migration with an unusual DEFAULT syntax.
"""

import glob
import json
import os
import re
import sys

_MIGRATIONS_GLOB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "src", "stratum", "db", "migrations", "*.sql"
)


def _load_defaults_and_uniques(migrations_glob: str = _MIGRATIONS_GLOB):
    """Scan the DuckDB migration SQL for column DEFAULTs and UNIQUE columns.

    Returns (defaults, uniques):
      defaults[table][column] = "<raw DEFAULT expression>"
      uniques[table] = {column, ...}   (single-column UNIQUE only — composite
                                         unique constraints aren't auto-recovered)
    """
    defaults: dict[str, dict[str, str]] = {}
    uniques: dict[str, set[str]] = {}

    def _default_for(table, col, expr):
        defaults.setdefault(table, {})[col] = expr.strip()

    def _unique_for(table, col):
        uniques.setdefault(table, set()).add(col)

    for path in sorted(glob.glob(migrations_glob)):
        sql = open(path, encoding="utf-8").read()

        # CREATE TABLE <name> ( ...column defs... );  — find the balanced body.
        for m in re.finditer(r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\(", sql):
            table = m.group(1)
            start = m.end()
            depth = 1
            i = start
            while i < len(sql) and depth > 0:
                if sql[i] == "(":
                    depth += 1
                elif sql[i] == ")":
                    depth -= 1
                i += 1
            body = sql[start : i - 1]

            for col_def in body.split(","):
                col_def = col_def.strip()
                cm = re.match(r'^"?(\w+)"?\s+[\w\[\]]+', col_def)
                if not cm:
                    continue
                col = cm.group(1)
                dm = re.search(
                    r"\bDEFAULT\s+('[^']*'|CURRENT_TIMESTAMP|TRUE|FALSE|-?\d+(?:\.\d+)?|\[\])",
                    col_def,
                    re.IGNORECASE,
                )
                if dm:
                    _default_for(table, col, dm.group(1))
                if re.search(r"\bUNIQUE\b", col_def, re.IGNORECASE):
                    _unique_for(table, col)

        # Standalone ALTER TABLE <name> ALTER COLUMN <col> SET DEFAULT <expr>
        for m in re.finditer(
            r"ALTER TABLE\s+(\w+)\s+ALTER(?:\s+COLUMN)?\s+(\w+)\s+SET\s+DEFAULT\s+"
            r"('[^']*'|CURRENT_TIMESTAMP|TRUE|FALSE|-?\d+(?:\.\d+)?|\[\])",
            sql,
            re.IGNORECASE,
        ):
            _default_for(*m.groups())

        # CREATE UNIQUE INDEX ... ON <table>(<col>)  — single-column only.
        for m in re.finditer(
            r"CREATE\s+UNIQUE\s+INDEX\s+\w+\s+ON\s+(\w+)\s*\(\s*(\w+)\s*\)", sql, re.IGNORECASE
        ):
            _unique_for(m.group(1), m.group(2))

    return defaults, uniques


# Pre-merge legacy duplicates superseded by the *_s / plural live tables.
SKIP_TABLES = {"substrate", "concept", "note", "_migrations"}

PK_OVERRIDE = {
    "share_tokens": "token",
    "blocked_ips": "ip_address",
    "user_profiles": "user_id",
    "changefeed": "seq",
    "changefeed_local": "seq",
    "arxiv_processed_papers": None,  # composite / no single PK — leave unconstrained
    "channel_processed_videos": None,
    "source_processed_items": None,
    "arxiv_subscriptions": "id",
}


def map_type(dt: str) -> str:
    dt = dt.strip()
    m = re.match(r"^FLOAT\[(\d+)\]$", dt)
    if m:
        return f"vector({m.group(1)})"
    if dt.endswith("[]"):
        return map_type(dt[:-2]) + "[]"
    base = {
        "VARCHAR": "TEXT",
        "JSON": "JSONB",
        "TIMESTAMP": "TIMESTAMPTZ",
        "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
        "FLOAT": "DOUBLE PRECISION",
        "DOUBLE": "DOUBLE PRECISION",
        "HUGEINT": "NUMERIC",
        "BIGINT": "BIGINT",
        "INTEGER": "INTEGER",
        "BOOLEAN": "BOOLEAN",
        "DATE": "DATE",
        "BLOB": "BYTEA",
    }
    return base.get(dt, "TEXT")  # safe fallback


def main() -> int:
    dump_path = sys.argv[1] if len(sys.argv) > 1 else "_schema_dump.json"
    schema = json.load(open(dump_path, encoding="utf-8"))
    defaults, uniques = _load_defaults_and_uniques()

    out = [
        "-- Generated by scripts/pg_schema_gen.py — P1.1 DB convergence (DuckDB -> PG).",
        "-- Non-destructive: creates the `stratum` schema; does NOT touch `aii`.",
        "-- DEFAULT/UNIQUE recovered from src/stratum/db/migrations/*.sql (see module docstring).",
        "CREATE EXTENSION IF NOT EXISTS vector;",
        "CREATE SCHEMA IF NOT EXISTS stratum;",
        "",
    ]
    tables = [t for t in sorted(schema) if t not in SKIP_TABLES]
    recovered_defaults = 0
    recovered_uniques = 0
    for t in tables:
        cols = schema[t]
        colnames = {c["col"] for c in cols}
        pk = PK_OVERRIDE.get(t, "id" if "id" in colnames else None)
        table_defaults = defaults.get(t, {})
        table_uniques = uniques.get(t, set())
        lines = []
        for c in cols:
            pg_type = map_type(c["type"])
            null = "" if c["null"] == "YES" else " NOT NULL"
            is_pk = pk and c["col"] == pk
            default_expr = table_defaults.get(c["col"])
            default_sql = f" DEFAULT {default_expr}" if default_expr and not is_pk else ""
            if default_sql:
                recovered_defaults += 1
            # PK implies NOT NULL; keep declaration clean.
            suffix = " PRIMARY KEY" if is_pk else null
            lines.append(f'    "{c["col"]}" {pg_type}{default_sql}{suffix}')
        out.append(f"CREATE TABLE IF NOT EXISTS stratum.{t} (")
        out.append(",\n".join(lines))
        out.append(");")
        out.append("")
        for uniq_col in sorted(table_uniques):
            if uniq_col == pk or uniq_col not in colnames:
                continue  # PK is already unique; skip columns not present after SKIP_TABLES/etc
            out.append(
                f'CREATE UNIQUE INDEX IF NOT EXISTS idx_{t}_{uniq_col}_unique ON stratum.{t}("{uniq_col}");'
            )
            recovered_uniques += 1
        if table_uniques:
            out.append("")
    print(
        f"-- {len(tables)} tables, skipped {sorted(SKIP_TABLES)}, "
        f"recovered {recovered_defaults} DEFAULTs + {recovered_uniques} UNIQUE constraints from migrations/",
        file=sys.stderr,
    )
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
