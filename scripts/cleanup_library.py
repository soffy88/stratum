"""
Library dedup + title cleanup script (§20 compliant).

Operations (all via admin API, no direct DB access):
  1. Delete bundle parent records (children already extracted as pq=ok)
  2. Delete pq=duplicate records
  3. Delete file_corrupt quarantine records + noise (Rick Astley, license)
  4. Strip z-lib tags from titles

Source of IDs: meta.duckdb.bak (read-only scan)
Target: live DB via PATCH/DELETE /api/v1/admin/

Usage:
  python3 /app/scripts/cleanup_library.py --dry-run    # preview counts
  python3 /app/scripts/cleanup_library.py --execute    # apply all changes
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import urllib.error

import duckdb

BAK_DB = "/root/.stratum/meta.duckdb.bak"
API_BASE = "http://127.0.0.1:9304"
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIwMUtWOEVSS0NCSk42SEE3TUJINUtKWEZCUSIsImlhdCI6MTc4MjQ4MzYwOCwiZXhwIjoxNzgyNTcwMDA4fQ"
    ".jjHvnZXiNZTjI53ZRFgx4oKGqNANqCCIQqJ23IeBgpE"
)

ZLIB_RE = re.compile(r"\s*\(z-lib[\w\.\s,\'-]*\)\s*", re.I)


# ── helpers ──────────────────────────────────────────────────────────────────

def api_call(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {JWT}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {body_text}") from e


def delete_substrate(sid: str, title: str, dry_run: bool) -> dict:
    if dry_run:
        return {"dry_run": True, "substrate_id": sid}
    return api_call("DELETE", f"/api/v1/admin/substrates/{sid}")


def bulk_title_update(updates: list[dict], dry_run: bool) -> dict:
    if dry_run:
        return {"dry_run": True, "count": len(updates)}
    return api_call("PATCH", "/api/v1/admin/substrates/bulk-title", {"updates": updates})


# ── data collection ───────────────────────────────────────────────────────────

def collect_from_backup() -> dict:
    conn = duckdb.connect(BAK_DB, read_only=True)

    bundles = conn.execute(
        "SELECT id, title FROM substrates WHERE parse_quality='bundle'"
    ).fetchall()

    dups = conn.execute(
        "SELECT id, title FROM substrates WHERE parse_quality='duplicate'"
    ).fetchall()

    file_corrupt = conn.execute(
        "SELECT id, title FROM substrates "
        "WHERE parse_quality='quarantine' AND quality_reason LIKE 'file_corrupt%'"
    ).fetchall()

    noise = conn.execute(
        "SELECT id, title FROM substrates "
        "WHERE parse_quality='quarantine' "
        "AND (title LIKE '%Rick Astley%' OR title='license' OR byte_size=0)"
    ).fetchall()

    # combine corrupt + noise, deduplicate by id
    to_delete_q: dict[str, str] = {}
    for r in file_corrupt + noise:
        to_delete_q[r[0]] = r[1]

    zlib_candidates = conn.execute(
        "SELECT id, title FROM substrates "
        "WHERE parse_quality NOT IN ('duplicate','bundle') "
        "AND parse_quality IS NOT NULL"
    ).fetchall()

    title_updates = []
    for r in zlib_candidates:
        orig = r[1] or ""
        new = ZLIB_RE.sub(" ", orig).strip()
        new = re.sub(r"\s+", " ", new).strip()
        if new != orig:
            title_updates.append({"id": r[0], "old": orig, "title": new})

    conn.close()
    return {
        "bundles": list(bundles),
        "dups": list(dups),
        "quarantine_delete": list(to_delete_q.items()),
        "title_updates": title_updates,
    }


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--execute", action="store_true", default=False)
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.print_help()
        sys.exit(1)

    dry_run = not args.execute

    print("Collecting IDs from backup DB…")
    data = collect_from_backup()

    bundles = data["bundles"]
    dups = data["dups"]
    q_delete = data["quarantine_delete"]
    title_updates = data["title_updates"]

    all_to_delete = [
        ("bundle", sid, title) for sid, title in bundles
    ] + [
        ("duplicate", sid, title) for sid, title in dups
    ] + [
        ("quarantine_corrupt", sid, title) for sid, title in q_delete
    ]

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
    print(f"  Bundle parents to delete:      {len(bundles)}")
    print(f"  Duplicate records to delete:   {len(dups)}")
    print(f"  Quarantine/corrupt to delete:  {len(q_delete)}")
    print(f"  Total deletions:               {len(all_to_delete)}")
    print(f"  Title z-lib cleanups:          {len(title_updates)}")

    if dry_run:
        print("\n[DRY RUN] Deletions:")
        for category, sid, title in all_to_delete:
            print(f"  [{category}] {sid}  {repr((title or '')[:55])}")
        print("\n[DRY RUN] Title updates (first 10):")
        for u in title_updates[:10]:
            print(f"  BEFORE: {repr(u['old'][:65])}")
            print(f"  AFTER:  {repr(u['title'][:65])}")
        print(f"  … and {len(title_updates)-10} more") if len(title_updates) > 10 else None
        return

    # — execute deletions —
    print("\nDeleting substrates…")
    ok = err = 0
    for category, sid, title in all_to_delete:
        try:
            result = delete_substrate(sid, title, dry_run=False)
            deleted = result.get("deleted_substrates", 0)
            status = "deleted" if deleted > 0 else "not_found"
            print(f"  {status}  [{category}] {sid}  {repr((title or '')[:45])}")
            ok += 1
        except RuntimeError as e:
            print(f"  ERROR  {sid}: {e}")
            err += 1

    print(f"\nDeletions: {ok} OK, {err} errors")

    # — execute title updates in batches of 50 —
    print("\nUpdating titles (z-lib cleanup)…")
    batch_size = 50
    total_updated = 0
    for i in range(0, len(title_updates), batch_size):
        batch = title_updates[i: i + batch_size]
        try:
            result = bulk_title_update(batch, dry_run=False)
            total_updated += result.get("updated", 0)
            print(f"  batch {i//batch_size+1}: {result.get('updated',0)} titles updated")
        except RuntimeError as e:
            print(f"  ERROR batch {i//batch_size+1}: {e}")

    print(f"\nTitle updates: {total_updated} total")
    print("\nDone.")


if __name__ == "__main__":
    main()
