"""★经济学飞轮(合并版,不再分 en/zh)— 发现未处理的经济书(任意语言).
扫 /home/soffy/books/MD/经济学/ → ≥3 章(第N章 或 # Chapter N)→
排除已入库(ingested_substrate ku>100)→ 排除 flywheel 终态 → 输出书单.

语言不再作为筛选,只决定 substrate_id 前缀(延续旧 id,避免已入库书被当新书重处理):
中文→econ_zh_<hash>,英文→econ_en_<hash>,特定已知书→固定 id。
用法: python scripts/econ_discover_all.py [--out list.txt] [--limit N] [--state state.json]
"""

import asyncio
import asyncpg
import json
import os
import re
import sys
import hashlib
import glob
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
# ★2026-08-29: from chapter_ingest 需要把 scripts/ 加进 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ECON_DIRS = [
    str(p)
    for p in (ROOT / "gdrive_staging" / "MD" / "经济学", Path("/home/soffy/books/MD/经济学"))
    if p.exists()
]

# 已有 substrate_id 的书 → 保留旧 id(避免重处理/孤儿)
KNOWN = {
    "Principles of Economics 10e": "mankiw_principles_econ_10e",
    "Principles of Microeconomics The Way We": "microecon_en_full_v2",
    "Principles of Microeconomics The Way We Live": "microecon_en_full_v2",
}


def _is_chinese(text: str) -> bool:
    samp = text[:200000]
    zh = len(re.findall(r"[一-鿿]", samp))
    en = len(re.findall(r"[A-Za-z]", samp))
    return zh > en


def _sid(stem: str, text: str) -> str:
    if stem in KNOWN:
        return KNOWN[stem]
    pref = "econ_zh" if _is_chinese(text) else "econ_en"
    return f"{pref}_{hashlib.md5(stem.encode('utf-8')).hexdigest()[:10]}"


def _chapters(text: str) -> int:
    # ★2026-08-29 优化: 之前调 chapter_starts 在大文件(4MB+ '诺贝尔经济学奖合集' 等
    # '套装书')上扫 6 个正则 + 跑 TOC 跳过逻辑, 30s+ 超时 -> discover 超时
    # 飞轮误判"无新书"。只测 n>=3 用快速两个正则(中文 + 英文), 仅候选书
    # 才会在预检/切章时调 chapter_starts 拿到完整起点表(8 KB / 数万行 不会超时)。
    cn = len(_CN_CHAP.findall(text))
    en = len(_EN_CHAP.findall(text))
    return max(cn, en)


_CN_CHAP = re.compile(
    r"(?m)^\s*#{0,4}\s*第([一二三四五六七八九十百千0-9]+)(章|单元|讲|课|节|部分|回|篇)"
)
# 与 econ_convert.chapters() / chapter_ingest 的宽格式保持一致：
# markitdown 常生成无冒号、全大写、或没有 Markdown '#' 的章节行。
_EN_CHAP = re.compile(r"(?mi)^\s*#{0,4}\s*(?:Chapter|CHAPTER)\s+\d+\b")


def discover() -> list[dict]:
    out = []
    for md in sorted(path for root in ECON_DIRS for path in glob.glob(f"{root}/*.md")):
        stem = Path(md).stem
        try:
            text = open(md, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        nch = _chapters(text)
        if nch < 3:  # 管道需 ≥3 章(无章节书 R1 会拒)
            continue
        out.append({"id": _sid(stem, text), "title": stem, "md_path": md, "chapters": nch})
    return out


async def _ingested(ids):
    if not ids:
        return set()
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # ★2026-10-14 热循环修复: 必须与 econ_batch_run.sh 的"已完整入库"判据一致
    # (登记 + BU + 至少1条KU)。之前只认 ku_count>100, 而 batch 对 1..100 KU 的书
    # 直接 SKIP(FORCE=0) → 书永远"待处理"又永远被跳过 → 飞轮每几秒空转一轮。
    rows = await conn.fetch(
        """
        SELECT s.substrate_id FROM aii.ingested_substrate s
        WHERE s.substrate_id = ANY($1::text[])
          AND (s.ku_count > 100
               OR (EXISTS (SELECT 1 FROM aii.bu_onto b WHERE b.substrate_id = s.substrate_id)
                   AND EXISTS (SELECT 1 FROM aii.ku_onto k WHERE k.substrate_id = s.substrate_id)))
        """,
        ids,
    )
    await conn.close()
    return {r["substrate_id"] for r in rows}


async def _thin(cands):
    """★2026-10-14: ids that look finished (state 'ingested' / DB complete) but sit below the
    absolute KU floor (ku_floor.thin_reason) -> retryable. Same rule as econ_batch_run.sh's
    skip check and the quality gate, so discover and batch never disagree (hot loop)."""
    from ku_floor import thin_reason

    if not cands:
        return {}
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        """
        SELECT substrate_id, count(*) AS ku,
               count(DISTINCT provenance->>'chapter') AS kch
        FROM aii.ku_onto WHERE substrate_id = ANY($1::text[]) GROUP BY substrate_id
        """,
        [c["id"] for c in cands],
    )
    await conn.close()
    stats = {r["substrate_id"]: (r["ku"], r["kch"]) for r in rows}
    out = {}
    for c in cands:
        ku, kch = stats.get(c["id"], (0, 0))
        reason = thin_reason(ku, kch, c.get("chapters"))
        if reason:
            out[c["id"]] = reason
    return out


async def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--state", default=str(ROOT / "econ_pipeline" / "flywheel_zh_state.json"))
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    cands = discover()
    if args.verbose:
        print(f"经济书候选(全语言): {len(cands)} 本", file=sys.stderr)
    state = {"processed": {}}
    if Path(args.state).exists():
        try:
            state = json.loads(Path(args.state).read_text(encoding="utf-8"))
        except Exception:
            pass
    done = {"ingested", "precheck_fail", "quarantine", "skip"}
    # ★2026-10-14: "ingested"/DB-complete books below the absolute KU floor are retryable.
    looks_done = [
        c for c in cands if state["processed"].get(c["id"], {}).get("status") in (None, "ingested")
    ]
    ing = await _ingested([c["id"] for c in looks_done])
    thin = await _thin(
        [
            c
            for c in looks_done
            if c["id"] in ing or state["processed"].get(c["id"], {}).get("status") == "ingested"
        ]
    )
    if args.verbose and thin:
        for sid, why in thin.items():
            print(f"  ↻ {sid} 低于KU绝对下限, 视为可重试: {why}", file=sys.stderr)
    cands = [
        c
        for c in cands
        if c["id"] in thin
        or (state["processed"].get(c["id"], {}).get("status") not in done and c["id"] not in ing)
    ]
    if args.verbose:
        print(f"排已入库/终态后: {len(cands)} 本", file=sys.stderr)
    if args.limit > 0:
        cands = cands[: args.limit]
    lines = [f"{c['md_path']}|{c['id']}|{c['title']}" for c in cands]
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"书单 → {args.out} ({len(lines)} 本)", file=sys.stderr)
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
