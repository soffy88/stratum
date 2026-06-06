"""AII Phase 1 export script.

Exports substrates with markdown derivative content to /data/shared/stratum-to-aii/.
Each substrate produces:
  <substrate_id>.md   — markdown content
  <substrate_id>.json — metadata (title, medium, source, published_at, created_at)

Run inside stratum-sl container:
  docker exec stratum-sl python3 /app/scripts/export_aii_samples.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

import duckdb

OUTPUT_DIR = Path("/data/shared/stratum-to-aii")
DB_PATH = os.environ.get("STRATUM_DB_PATH", "/root/.stratum/meta.duckdb")


def main():
    if not OUTPUT_DIR.exists():
        print(f"ERROR: output dir {OUTPUT_DIR} not mounted", file=sys.stderr)
        sys.exit(1)

    conn = duckdb.connect(DB_PATH, read_only=True)
    rows = conn.execute("""
        SELECT
            s.id,
            s.title,
            json_extract_string(s.meta_json, '$.medium') AS medium,
            s.source,
            s.published_at,
            s.created_at,
            d.content
        FROM substrates s
        JOIN derivative d
          ON d.substrate_id = s.id
         AND d.kind = 'markdown'
         AND d.content IS NOT NULL
         AND d.content != ''
        ORDER BY s.created_at DESC
    """).fetchall()
    conn.close()

    cols = ["id", "title", "medium", "source", "published_at", "created_at", "content"]
    exported = 0
    for row in rows:
        item = dict(zip(cols, row))
        sid = item["id"]

        md_path = OUTPUT_DIR / f"{sid}.md"
        md_path.write_text(item["content"], encoding="utf-8")

        meta = {
            k: v.isoformat() if hasattr(v, "isoformat") else v
            for k, v in item.items()
            if k != "content"
        }
        json_path = OUTPUT_DIR / f"{sid}.json"
        json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        print(
            f"exported {sid[:16]}... title={item['title']!r} medium={item['medium']} content_len={len(item['content'])}"
        )
        exported += 1

    print(f"\nDone: {exported} substrates exported to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
