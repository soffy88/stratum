#!/usr/bin/env python3
"""Requeue books that reached a terminal state without producing any KU.

This is deliberately reversible: it only changes flywheel checkpoint JSON and
leaves quarantine records, source files, BU rows, and KU rows untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg


ROOT = Path(__file__).resolve().parents[1]
STATE_FILES = sorted(ROOT.glob("*_pipeline/*flywheel*state.json"))


async def main(apply: bool) -> int:
    conn = await asyncpg.connect("postgresql://aii:aii_safe_pass@localhost:5437/aii_kg")
    changed = 0
    for path in STATE_FILES:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        processed = data.get("processed")
        if not isinstance(processed, dict):
            continue
        updates = []
        for sid, item in processed.items():
            if not isinstance(item, dict) or item.get("status") not in {"quarantine", "skip"}:
                continue
            n = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sid)
            if n:
                continue
            updates.append((sid, item.get("status"), item.get("reason", "")))
        if not updates:
            continue
        print(f"{path}: {len(updates)} zero-KU terminal records")
        for sid, old, reason in updates:
            print(f"  {sid}: {old} -> retry ({reason[:100]})")
            processed[sid] = {
                **processed[sid],
                "status": "retry",
                "retry_reason": "zero_ku_terminal_recovery",
            }
        changed += len(updates)
        if apply:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
    await conn.close()
    print(f"total={changed} {'applied' if apply else 'dry-run'}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
