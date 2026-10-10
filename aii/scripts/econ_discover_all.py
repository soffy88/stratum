"""★经济学飞轮(合并版,不再分 en/zh)— 发现未处理的经济书(任意语言).
扫 /home/soffy/books/MD/经济学/ → ≥3 章(第N章 或 # Chapter N)→
排除已入库(ingested_substrate ku>100)→ 排除 flywheel 终态 → 输出书单.

语言不再作为筛选,只决定 substrate_id 前缀(延续旧 id,避免已入库书被当新书重处理):
中文→econ_zh_<hash>,英文→econ_en_<hash>,特定已知书→固定 id。
用法: python scripts/econ_discover_all.py [--out list.txt] [--limit N] [--state state.json]
"""

import asyncio, asyncpg, json, os, re, sys, hashlib, glob
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
ECON_DIR = "/home/soffy/books/MD/经济学"

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
    # ★口径统一: 直接用 chapter_ingest.chapter_starts——下游预检(econ_batch_run.sh 的
    # PASS_ZH 兜底)和切章用的就是它(含 第N章/# Chapter N:/N.M小节编号三种风格)。
    # 之前这里自带窄正则, OpenStax 等"N.M 小节编号"排版的书(拉书回流的主要产物)数出
    # 0 章被永久静默跳过——书进了池没人捡, 最后一公里断在这。
    from chapter_ingest import chapter_starts
    return len(chapter_starts(text))


def discover() -> list[dict]:
    out = []
    for md in sorted(glob.glob(f"{ECON_DIR}/*.md")):
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
    rows = await conn.fetch(
        "SELECT substrate_id FROM aii.ingested_substrate WHERE substrate_id=ANY($1::text[]) AND ku_count>100",
        ids,
    )
    await conn.close()
    return {r["substrate_id"] for r in rows}


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
    cands = [c for c in cands if state["processed"].get(c["id"], {}).get("status") not in done]
    ing = await _ingested([c["id"] for c in cands])
    cands = [c for c in cands if c["id"] not in ing]
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
