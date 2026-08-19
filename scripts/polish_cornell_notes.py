#!/usr/bin/env python3
"""批量润色康奈尔笔记: 默认只补 drills; --nim 才调 NIM 润色线索/总结。

  PYTHONPATH=src STRATUM_PG_PASSWORD=aii_safe_pass \\
    aii/.venv/bin/python scripts/polish_cornell_notes.py --limit 45
  ... --nim --limit 5   # NIM 40rpm/key, 少量试跑
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
os.environ.setdefault("STRATUM_PG_HOST", "127.0.0.1")
os.environ.setdefault("STRATUM_PG_PORT", "5435")
os.environ.setdefault("STRATUM_PG_USER", "aii")
os.environ.setdefault("STRATUM_PG_PASSWORD", "aii_safe_pass")
os.environ.setdefault("STRATUM_PG_DB", "aii_kg")

from stratum.db import query, update  # noqa: E402
from stratum.services.cornell_polish import build_drills, polish_content  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--nim", action="store_true", help="调用 NIM 润色(40rpm/key)")
    ap.add_argument("--id", action="append", default=[])
    args = ap.parse_args()

    if args.id:
        rows = []
        for nid in args.id:
            r = query(
                "SELECT id, title, content FROM cornell_notes WHERE id=%(id)s AND deleted_at IS NULL",
                {"id": nid},
            )
            rows.extend(r)
    else:
        rows = query(
            """
            SELECT id, title, content FROM cornell_notes
            WHERE deleted_at IS NULL AND source='machine'
            ORDER BY updated_at DESC LIMIT %(lim)s
            """,
            {"lim": args.limit},
        )

    ok = fail = 0
    for r in rows:
        content = r["content"]
        if isinstance(content, str):
            content = json.loads(content)
        try:
            if args.nim:
                content = polish_content(content)
            content["drills"] = build_drills(content)
            update(
                "cornell_notes",
                r["id"],
                {
                    "content": json.dumps(content, ensure_ascii=False),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            print(f"  ok {r['id'][:20]} · {r['title'][:40]} drills={len(content.get('drills') or [])}")
            ok += 1
        except Exception as e:
            print(f"  ERR {r['id']}: {e}")
            fail += 1
    print(f"done ok={ok} fail={fail} nim={args.nim}")


if __name__ == "__main__":
    main()
