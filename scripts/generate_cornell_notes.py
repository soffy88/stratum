#!/usr/bin/env python3
"""从 B仓核心概念批量生成康奈尔笔记, 写入 stratum.cornell_notes。

用法:
  cd /data/soffy/projects/stratum
  STRATUM_PG_PASSWORD=aii_safe_pass .venv/bin/python scripts/generate_cornell_notes.py
  .venv/bin/python scripts/generate_cornell_notes.py --discipline math --limit 30
  .venv/bin/python scripts/generate_cornell_notes.py --concept-id 123
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# DB env defaults for local
os.environ.setdefault("STRATUM_PG_HOST", "127.0.0.1")
os.environ.setdefault("STRATUM_PG_PORT", "5435")
os.environ.setdefault("STRATUM_PG_USER", "aii")
os.environ.setdefault("STRATUM_PG_PASSWORD", "aii_safe_pass")
os.environ.setdefault("STRATUM_PG_DB", "aii_kg")

from stratum.db import insert, read, update  # noqa: E402
from stratum.services.cornell_generator import (  # noqa: E402
    generate_for_concept,
    list_core_concept_ids,
    stable_note_id,
)


def upsert_machine(gen: dict) -> str:
    note_id = stable_note_id(gen["topic_id"], "machine")
    ts = datetime.now(timezone.utc)
    payload = {
        "title": gen["title"],
        "subject": gen["subject"],
        "refined_ku_ids": json.dumps(gen["refined_ku_ids"], ensure_ascii=False),
        "refined_concept_ids": json.dumps(gen["refined_concept_ids"], ensure_ascii=False),
        "content": json.dumps(gen["content"], ensure_ascii=False),
        "updated_at": ts,
        "deleted_at": None,
    }
    existing = read("cornell_notes", note_id)
    if existing:
        update("cornell_notes", note_id, payload)
        return f"updated {note_id}"
    insert(
        "cornell_notes",
        {
            "id": note_id,
            "topic_id": gen["topic_id"],
            "source": "machine",
            "user_id": None,
            "created_at": ts,
            **payload,
        },
    )
    return f"created {note_id}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discipline", default=None)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-kus", type=int, default=8)
    ap.add_argument("--concept-id", type=int, action="append", default=[])
    args = ap.parse_args()

    ids = list(args.concept_id)
    if not ids:
        ids = list_core_concept_ids(discipline=args.discipline, limit=args.limit)
    print(f"concepts={len(ids)} discipline={args.discipline or 'all'}")

    ok = fail = 0
    for cid in ids:
        try:
            gen = generate_for_concept(cid, max_kus=args.max_kus)
            if not gen:
                print(f"  skip {cid}: no kus")
                fail += 1
                continue
            msg = upsert_machine(gen)
            print(f"  {msg} · {gen['title'][:40]} ({gen['subject']})")
            ok += 1
        except Exception as e:
            print(f"  ERR {cid}: {e}")
            fail += 1
    print(f"done ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
