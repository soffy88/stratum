import duckdb
import os
import glob

def run_migrations():
    db_path = os.path.expanduser("~/.stratum/meta.duckdb")
    conn = duckdb.connect(db_path)
    migration_files = sorted(glob.glob("/home/soffy/projects/platform/stratum/src/stratum/db/migrations/*.sql"))
    try:
        current_migrations = [r[0] for r in conn.execute("SELECT filename FROM _migrations").fetchall()]
    except:
        conn.execute("CREATE TABLE _migrations (filename VARCHAR PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        current_migrations = []
    for sql_file in migration_files:
        name = os.path.basename(sql_file)
        if name not in current_migrations:
            print(f"Applying migration: {name}")
            with open(sql_file, 'r') as f:
                conn.execute(f.read())
            conn.execute("INSERT INTO _migrations (filename) VALUES (?)", (name,))
    conn.close()

if __name__ == "__main__":
    run_migrations()
