"""★论文飞轮 — 发现未处理的论文.
扫 /home/soffy/books/MD/论文/*.md(classify_md.py 新分出的桶——doc_type=paper 但非
"讲义型"的普通论文, 之前被判"低质"永久扔在 stratum-to-aii, 现在真正有消费者)
→ 排除已入库/终态 → 输出书单.

论文≠教材, 不需要凑章节结构(见 docs/PAPER_BU_SCHEMA.md)——不像 advmath_discover.py
那样要求 chapter_numbers()>=3, 只要不是空文件就够, paper_pipeline.sh 走的是
generate_bu.py 的论文分支(读全文首尾+节标题出BU卡), 不做逐章切分。

substrate_id: paper_<hash>。"已处理"判据用 deep_understood_at(BU 是否生成),
不用 ku_count(论文管道刻意不产 KU, 见 paper_pipeline.sh, ku_count=0 是正常状态,
不能拿来判"是否处理过"——那样会导致同一篇论文每轮都被当新书重跑)。

用法: python scripts/paper_discover.py [--out list.txt] [--limit N] [--state state.json]
"""

import asyncio
import asyncpg
import json
import os
import sys
import hashlib
import glob
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

PAPER_DIRS = [
    str(p)
    for p in (ROOT / "gdrive_staging" / "MD" / "论文", Path("/home/soffy/books/MD/论文"))
    if p.exists()
]


def _sid(stem: str) -> str:
    return f"paper_{hashlib.md5(stem.encode('utf-8')).hexdigest()[:10]}"


def discover() -> list[dict]:
    out = []
    for md in sorted(path for root in PAPER_DIRS for path in glob.glob(f"{root}/*.md")):
        stem = Path(md).stem
        try:
            n = Path(md).stat().st_size
        except Exception:
            continue
        if n < 1000:  # 空壳/读取失败的残渣, 不当候选
            continue
        out.append({"id": _sid(stem), "title": stem, "md_path": md})
    return out


async def _ingested(ids):
    if not ids:
        return set()
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT substrate_id FROM aii.ingested_substrate "
        "WHERE substrate_id=ANY($1::text[]) AND deep_understood_at IS NOT NULL",
        ids,
    )
    await conn.close()
    return {r["substrate_id"] for r in rows}


def _state_blocks(entry: dict) -> bool:
    """Allow old transient quarantines to retry after service recovery."""
    status = (entry or {}).get("status", "")
    if status in {"precheck_fail", "skip"}:
        return True
    if status != "quarantine":
        return False
    stamp = (entry or {}).get("ts")
    if not stamp:
        return False
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        cooldown = int(os.getenv("AII_QUARANTINE_RETRY_MINUTES", "30"))
        return datetime.now(timezone.utc) - when < timedelta(minutes=max(0, cooldown))
    except (TypeError, ValueError, OverflowError):
        return False


async def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--state", default=str(ROOT / "paper_pipeline" / "flywheel_state.json"))
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    cands = discover()
    if args.verbose:
        print(f"论文候选: {len(cands)} 篇", file=sys.stderr)
    state = {"processed": {}}
    if Path(args.state).exists():
        try:
            state = json.loads(Path(args.state).read_text(encoding="utf-8"))
        except Exception:
            pass
    cands = [c for c in cands if not _state_blocks(state["processed"].get(c["id"], {}))]
    ing = await _ingested([c["id"] for c in cands])
    cands = [c for c in cands if c["id"] not in ing]
    if args.verbose:
        print(f"排已入库/终态后: {len(cands)} 篇", file=sys.stderr)
    if args.limit > 0:
        cands = cands[: args.limit]
    # ★2026-08-16: 分隔符从 `|` 改 TAB — 实测论文 md 文件名含 `|`(如
    #   All_parallel_chip-firing_games_with_$2|E_01KZB25B.md)会把 `|` 协议读错位,
    #   substrate 错成文件名尾段、正确 id 落进 title 字段, 污染 ingested_substrate。
    #   TAB 不可能出现在文件路径/名中, 解析不再可能错位。
    lines = [f"{c['md_path']}\t{c['id']}\t{c['title']}" for c in cands]
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"书单 → {args.out} ({len(lines)} 篇)", file=sys.stderr)
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
