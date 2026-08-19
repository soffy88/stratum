#!/usr/bin/env python3
"""A 仓存量补填 (P1.3) — 为历史 KU 生成 grounded_by 引用链 + fingerprint。

存量 KU 是管道升级前入库的(无引用链) —— 引用链可从 ku_id 确定性解析
(substrate_id 已知; chapter_anchor 从 `::chN::`/`::N::` 段解析)。
extraction_method 诚实标注 'legacy_ingest'。零 LLM, 幂等(已填跳过)。

用法:
    .venv/bin/python scripts/backfill_grounded_by.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

from ku_schema import build_grounded_by, ku_fingerprint, parse_chapter_anchor

DSN = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = await asyncpg.connect(DSN)
    rows = await conn.fetch(
        "SELECT ku_id, substrate_id, natural_text FROM aii.ku_onto"
        " WHERE grounded_by IS NULL OR grounded_by->>'method' = 'default'"
        " ORDER BY created_at"
        + (" LIMIT $1" if args.limit else ""),
        *([args.limit] if args.limit else []),
    )
    print(f"待补填: {len(rows)} 条", flush=True)

    ok = 0
    for r in rows:
        ch = parse_chapter_anchor(r["ku_id"])
        packet = build_grounded_by(
            r["substrate_id"], ch,
            parser_version="legacy",
            extraction_method="legacy_ingest",
        )
        fp = ku_fingerprint(r["natural_text"] or "")
        if args.dry_run:
            ok += 1
            continue
        await conn.execute(
            "UPDATE aii.ku_onto SET grounded_by=$1, fingerprint=$2, updated_at=now()"
            " WHERE ku_id=$3",
            json.dumps(packet, ensure_ascii=False), fp, r["ku_id"],
        )
        ok += 1
        if ok % 5000 == 0:
            print(f"  ...{ok}/{len(rows)}", flush=True)

    await conn.close()
    print(f"完成: {ok}/{len(rows)} 条 ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
