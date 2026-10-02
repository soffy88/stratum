"""Attach an unambiguous uploaded binary to a stale canonical substrate.

Run with the production-like storage mount and authenticated owner identity:
  python scripts/reconcile_source_binary.py SOURCE_ID USER_ID
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from stratum.db import get_conn
from stratum.services.source_storage import attach_original_binary
from stratum.utils.user_id_hash import hash_user_id


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id")
    parser.add_argument("user_id")
    args = parser.parse_args()
    owner_hash = hash_user_id(args.user_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id, title, source_path, file_hash, mime, byte_size FROM substrates WHERE id=? AND user_id=?",
            (args.source_id, owner_hash),
        ).fetchone()
    if not row:
        raise SystemExit("source not found or not owned by authenticated user")
    expected = row[4]
    root = Path(os.environ.get("STRATUM_DATA_DIR", str(Path.home() / ".stratum")))
    # Immutable originals are authoritative.  Inbox is only a recovery source
    # when no durable copy exists; repeated temporary uploads must not make a
    # previously resolved source ambiguous.
    durable = root / "originals" / owner_hash
    durable_matches = [p for p in durable.rglob("*") if p.is_file() and _hash(p) == expected] if durable.is_dir() else []
    if durable_matches:
        matches = durable_matches
    else:
        inbox = root / "users" / args.user_id / "inbox"
        candidates = [p for p in inbox.rglob("*") if p.is_file()] if inbox.is_dir() else []
        matches = [p for p in candidates if _hash(p) == expected]
    if len(matches) != 1:
        print({"status": "missing" if not matches else "ambiguous", "matches": len(matches)})
        return 2
    attached = attach_original_binary(
        args.source_id,
        args.user_id,
        matches[0],
        content_hash=expected,
        mime_type="application/pdf" if matches[0].suffix.lower() == ".pdf" else row[5],
    )
    print({"status": "resolved", "source_id": args.source_id, "old_storage_ref": row[3], "new_storage_ref": attached["uri"], "expected_hash": expected, "actual_hash": attached["hash"], "owner_match": True, "mime": "application/pdf" if matches[0].suffix.lower() == ".pdf" else row[5]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
