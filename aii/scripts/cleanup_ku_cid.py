#!/usr/bin/env python3
"""存量 KU 清洗 — 清 (cid:NNN) PDF 码点污染 + 字母粘连启发式修复 + 重算 fingerprint。

用法:
    cd aii && .venv/bin/python scripts/cleanup_ku_cid.py [--dry-run] [--limit N] [--substrate PREFIX]

只更新 natural_text / title 两列(不碰 embedding/grade 等); fingerprint 重算为
sha256(natural_text) 前缀, 用于后续去重。--dry-run 只看不改。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys

import asyncpg

_CID_RE = re.compile(r"\(cid:\d+\)")
_CAMEL_RE = re.compile(r"([a-z])([A-Z])")


def fix_text(s: str) -> str:
    s = _CID_RE.sub("", s)
    return _CAMEL_RE.sub(r"\1 \2", s)


def fp(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:40]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--substrate", default="")
    args = ap.parse_args()

    import os
    dsn = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    conn = await asyncpg.connect(dsn)

    cond = "natural_text LIKE '%(cid:%'"
    if args.substrate:
        cond += f" AND substrate_id LIKE '{args.substrate}%'"
    rows = await conn.fetch(f"SELECT ku_id, title, natural_text FROM aii.ku_onto WHERE {cond}")
    if args.limit:
        rows = rows[: args.limit]

    changed = skipped = 0
    for r in rows:
        nt2 = fix_text(r["natural_text"])
        t2 = fix_text(r["title"] or "")
        if nt2 == r["natural_text"] and t2 == (r["title"] or ""):
            skipped += 1
            continue
        changed += 1
        if args.dry_run:
            print(f"[dry] {r['ku_id']}\n  title: {r['title'][:40]!r} -> {t2[:40]!r}\n  nt:    {r['natural_text'][:60]!r} -> {nt2[:60]!r}")
            continue
        await conn.execute(
            "UPDATE aii.ku_onto SET natural_text=$1, title=$2, fingerprint=$3, "
            "updated_at=now() WHERE ku_id=$4",
            nt2, t2, fp(nt2), r["ku_id"],
        )
    await conn.close()
    print(f"命中 {len(rows)} 条: 修改 {changed} / 无变化 {skipped} ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
