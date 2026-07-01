#!/usr/bin/env python3
"""Copy Stratum's relational data DuckDB -> PostgreSQL `stratum` schema (P1.3).

Run with stratum-sl STOPPED (DuckDB single-writer lock). Reads each live table
from DuckDB and bulk-inserts into the matching stratum.<table> in aii-postgres.

- Vector columns (FLOAT[N]) are SKIPPED — content is re-embedded with BGE-M3 in P1.4.
- JSON columns -> jsonb (cast on insert).
- Array columns (TEXT[]) -> psycopg2 adapts python lists natively.
- Each target table is TRUNCATEd first, so the script is re-runnable.

Env:
  STRATUM_DB_PATH   DuckDB path (default ~/.stratum/meta.duckdb)
  PG_HOST/PG_PORT/PG_USER/PG_PASSWORD/PG_DB  target PG (stratum schema)
"""
import json
import os
import re
import sys

import duckdb
import psycopg2
from psycopg2.extras import execute_values

SKIP_TABLES = {"substrate", "concept", "note", "_migrations"}


def col_kinds(cols):
    """Return (insert_cols, jsonb_set) for a table's column dicts."""
    insert_cols, jsonb = [], set()
    for c in cols:
        t = c["type"]
        if re.match(r"^FLOAT\[\d+\]$", t):
            continue  # vector — skip, re-embed in P1.4
        insert_cols.append(c["col"])
        if t == "JSON":
            jsonb.add(c["col"])
    return insert_cols, jsonb


def main() -> int:
    schema = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "_schema_dump.json",
                             encoding="utf-8"))
    duck = duckdb.connect(os.path.expanduser(
        os.environ.get("STRATUM_DB_PATH", "~/.stratum/meta.duckdb")), read_only=True)
    pg = psycopg2.connect(
        host=os.environ["PG_HOST"], port=int(os.environ.get("PG_PORT", "5435")),
        user=os.environ["PG_USER"], password=os.environ["PG_PASSWORD"],
        dbname=os.environ["PG_DB"], options="-c search_path=stratum",
    )
    pg.autocommit = False
    cur = pg.cursor()

    total = 0
    for t in sorted(schema):
        if t in SKIP_TABLES:
            continue
        cols = schema[t]
        insert_cols, jsonb = col_kinds(cols)
        rows = duck.execute(
            f"SELECT {', '.join(insert_cols)} FROM {t}").fetchall()
        cur.execute(f"TRUNCATE stratum.{t}")
        if not rows:
            print(f"  {t}: 0")
            continue
        # Build per-column value templates: jsonb cols get ::jsonb cast.
        tmpl = "(" + ", ".join(
            "%s::jsonb" if c in jsonb else "%s" for c in insert_cols) + ")"
        # Normalize jsonb values: dict/list -> json string; keep str/None as-is.
        ji = [i for i, c in enumerate(insert_cols) if c in jsonb]
        norm = []
        for r in rows:
            r = list(r)
            for i in ji:
                v = r[i]
                if v is not None and not isinstance(v, str):
                    r[i] = json.dumps(v, ensure_ascii=False)
            norm.append(tuple(r))
        collist = ", ".join(f'"{c}"' for c in insert_cols)
        execute_values(
            cur, f"INSERT INTO stratum.{t} ({collist}) VALUES %s",
            norm, template=tmpl, page_size=1000)
        print(f"  {t}: {len(rows)}")
        total += len(rows)

    pg.commit()
    print(f"DONE — {total} rows migrated")
    cur.close(); pg.close(); duck.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
