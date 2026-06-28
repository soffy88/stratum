#!/usr/bin/env python3
"""Rebuild / purge search indexes so they match the live substrates table.

Why: the DB merge deleted substrates without reindexing, leaving the tantivy &
lancedb indexes full of "ghost" entries (hits whose substrate no longer exists).
Ghosts crowd out real results and show empty title/highlight.

What it does (run with stratum-sl STOPPED — DuckDB single-writer lock):
  - Tantivy: FULL rebuild. Wipe the index dir (renamed to .bak first) and re-add
    one doc per live substrate. Embedding-independent → always safe.
  - Lancedb: PURGE ghosts only. Delete vector records whose substrate_id is not in
    the substrates table. Existing embeddings are kept untouched (no model mixing).
    Re-embedding live substrates that lack vectors is a SEPARATE step
    (scripts/batch_reembed.py) because it must use one consistent embedding model.

§20: only calls oprim/oskill public APIs; does not modify the main libs.

Usage (inside a container that mounts ~/.stratum):
    docker stop stratum-sl
    docker exec ...        # or: docker run --rm -v ~/.stratum:/root/.stratum <image> \
        python3 /app/scripts/rebuild_indexes.py --report      # dry run, no writes
        python3 /app/scripts/rebuild_indexes.py --apply       # do it
    docker start stratum-sl
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, "/app/src")


def _live_substrates(conn) -> dict[str, dict]:
    """{id: {title, content}} for every row in substrates, best derivative content."""
    rows = conn.execute(
        "SELECT s.id, s.title, ("
        "  SELECT substr(d.content, 1, 10000) FROM derivative d "
        "  WHERE d.substrate_id = s.id AND d.content IS NOT NULL AND length(d.content) > 0 "
        "  ORDER BY (d.kind = 'markdown') DESC, length(d.content) DESC LIMIT 1"
        ") FROM substrates s"
    ).fetchall()
    return {r[0]: {"title": r[1], "content": r[2] or ""} for r in rows}


def _rebuild_tantivy(live: dict[str, dict], apply: bool) -> None:
    from oskill.knowledge._context import tantivy_path
    from oprim.fulltext import open_fulltext_index
    from oprim.fulltext.tantivy import FulltextDoc

    path = tantivy_path()
    print(f"[tantivy] path={path}  live_substrates={len(live)}")
    if not apply:
        print("[tantivy] (report) would wipe + re-add one doc per live substrate")
        return

    if path.exists():
        bak = path.with_suffix(".bak")
        if bak.exists():
            shutil.rmtree(bak)
        shutil.move(str(path), str(bak))
        print(f"[tantivy] old index moved to {bak}")

    path.mkdir(parents=True, exist_ok=True)
    idx = open_fulltext_index(path)
    docs, added = [], 0
    for sid, m in live.items():
        title = m["title"] or sid
        docs.append(FulltextDoc(id=sid, fields={"title": title, "content": m["content"][:10000]}))
        if len(docs) >= 200:
            idx.add(docs); added += len(docs); docs = []
    if docs:
        idx.add(docs); added += len(docs)
    print(f"[tantivy] rebuilt: {added} docs indexed")


def _purge_lancedb(live: set[str], apply: bool) -> None:
    from oskill.knowledge._context import lancedb_path
    import lancedb

    path = lancedb_path()
    print(f"[lancedb] path={path}")
    db = lancedb.connect(str(path))
    if "vectors_text" not in db.table_names():
        print("[lancedb] table 'vectors_text' missing — nothing to purge")
        return
    tbl = db.open_table("vectors_text")
    ids = [r["id"] for r in tbl.search().limit(10_000_000).select(["id"]).to_list()]
    ghosts = [rid for rid in ids if rid.split("#", 1)[0] not in live]
    kept = len(ids) - len(ghosts)
    print(f"[lancedb] total={len(ids)}  live_kept={kept}  ghosts={len(ghosts)}")
    if not apply:
        print("[lancedb] (report) would delete the ghost records")
        return
    # Delete in batches to keep the IN(...) predicate small (~0.4s per 2000).
    for i in range(0, len(ghosts), 2000):
        batch = ghosts[i:i + 2000]
        quoted = ",".join("'" + rid.replace("'", "''") + "'" for rid in batch)
        tbl.delete(f"id IN ({quoted})")
    print(f"[lancedb] deleted {len(ghosts)} ghost records")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true", help="dry run, no writes")
    g.add_argument("--apply", action="store_true", help="rebuild tantivy + purge lancedb ghosts")
    args = ap.parse_args()
    apply = args.apply

    import duckdb

    db_path = os.path.expanduser(os.environ.get("STRATUM_DB_PATH", "~/.stratum/meta.duckdb"))
    print(f"[db] {db_path} (read_only)")
    conn = duckdb.connect(db_path, read_only=True)
    try:
        live = _live_substrates(conn)
    finally:
        conn.close()
    print(f"[db] live substrates: {len(live)}")
    with_content = sum(1 for m in live.values() if m["content"])
    print(f"[db] with non-empty content: {with_content}")

    _rebuild_tantivy(live, apply)
    _purge_lancedb(set(live), apply)
    print("DONE" + ("" if apply else " (report only — re-run with --apply)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
