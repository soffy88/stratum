import glob
import os


def run_migrations():
    """No-op on the PostgreSQL backend (AII merge P1.x).

    The store is now aii-postgres `stratum` schema, created via
    `scripts/pg_schema_gen.py` → `src/stratum/db/pg_schema/`. The old DuckDB
    migration runner is obsolete and would spin up a stray DuckDB file at
    startup, so it is intentionally skipped. The legacy DuckDB runner is kept
    below under `_run_duckdb_migrations` for reference / rollback.
    """
    return


def _run_duckdb_migrations():  # legacy, unused on PG
    import duckdb

    db_path = os.path.expanduser("~/.stratum/meta.duckdb")
    conn = duckdb.connect(db_path)
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    try:
        current_migrations = [
            r[0] for r in conn.execute("SELECT filename FROM _migrations").fetchall()
        ]
    except Exception:
        conn.execute(
            "CREATE TABLE _migrations (filename VARCHAR PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        current_migrations = []
    for sql_file in migration_files:
        name = os.path.basename(sql_file)
        if name not in current_migrations:
            print(f"Applying migration: {name}")
            with open(sql_file, "r") as f:
                conn.execute(f.read())
            conn.execute("INSERT INTO _migrations (filename) VALUES (?)", (name,))
    conn.close()


if __name__ == "__main__":
    run_migrations()
