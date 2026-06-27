"""发现未处理的经济金融类书籍并输出书单.

用途: 供 econ_flywheel.sh 调用, 生成当次要处理的书单文件.

算法:
  1. 扫 /home/soffy/shared/stratum-to-aii/*.json (sidecar)
  2. 过滤 medium==book + 经济金融关键词
  3. 按标题去重 (同标题取 id 最小/最早的那条)
  4. 从 flywheel_state.json 排除已终态(ingested/precheck_fail/quarantine)
  5. 从 DB 排除已完整入库 (ku>100 AND bu>0) 的
  6. 输出 `md绝对路径|substrate_id|书名` 格式的书单到 stdout

Usage:
  python scripts/econ_discover.py [--out /path/to/list.txt] [--limit N]
"""
import asyncio, asyncpg, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

STRATUM_DIR = Path("/home/soffy/shared/stratum-to-aii")
STATE_FILE = ROOT / "econ_pipeline" / "flywheel_state.json"

ECON_KEYWORDS = [
    "经济", "economics", "econom", "macro", "micro", "金融", "finance", "financial",
    "货币", "monetary", "宏观", "微观", "计量", "econometric", "banking", "bank",
    "贸易", "trade", "资本", "capital", "价格", "price", "投资", "invest",
    "统计", "statistic", "管理经济", "劳动经济", "产业", "市场", "market",
]
SKIP_KEYWORDS = [
    "数学教你", "数学家的", "德国一流大学", "哲学", "philosophy",
    "manipulation", "psychology", "心理", "技术大全",
]


def _is_econ(title: str) -> bool:
    t = title.lower()
    if any(k.lower() in t for k in SKIP_KEYWORDS):
        return False
    return any(k.lower() in t for k in ECON_KEYWORDS)


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"processed": {}}


def discover_candidates() -> list[dict]:
    """返回 [{id, title, md_path}] 列表(已去重/已过滤学科).

    优先使用 {id}_structured.md (Stratum重新输出的规范结构版),
    fallback 到 {id}.md (原始版).
    """
    by_title: dict[str, dict] = {}
    for f in sorted(STRATUM_DIR.glob("*.json")):
        # 跳过 sidecar/structured 文件(只读 plain *.json)
        if f.stem.endswith("_structured") or ".sidecar" in f.name:
            continue
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("medium") != "book":
            continue
        title = meta.get("title") or ""
        if not _is_econ(title):
            continue
        sid = meta["id"]
        # 优先用 _structured.md(Stratum规范重出), fallback 原始 .md
        structured_md = STRATUM_DIR / (sid + "_structured.md")
        original_md = STRATUM_DIR / (sid + ".md")
        if structured_md.exists():
            md_path = structured_md
        elif original_md.exists():
            md_path = original_md
        else:
            continue
        # 同标题取 ID 最小的(最早产出)
        if title not in by_title or sid < by_title[title]["id"]:
            by_title[title] = {"id": sid, "title": title, "md_path": str(md_path)}
    return list(by_title.values())


async def _ingested_set(candidates: list[dict]) -> set[str]:
    """从 DB 查哪些已完整入库 (ku>100 AND bu>0)."""
    ids = [c["id"] for c in candidates]
    if not ids:
        return set()
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("""
        SELECT substrate_id
        FROM aii.ingested_substrate
        WHERE substrate_id = ANY($1::text[])
          AND ku_count > 100
          AND (SELECT count(*) FROM aii.bu_onto WHERE substrate_id=ingested_substrate.substrate_id) > 0
    """, ids)
    await conn.close()
    return {r["substrate_id"] for r in rows}


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="输出书单文件路径(默认stdout)")
    ap.add_argument("--limit", type=int, default=0, help="最多输出N本(0=全部)")
    ap.add_argument("--include-done", action="store_true", help="包含已处理的书")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    candidates = discover_candidates()
    if args.verbose:
        print(f"扫描经济书候选: {len(candidates)} 本 (去重后)", file=sys.stderr)

    # 排除 flywheel 已终态
    state = _load_state()
    done_states = {"ingested", "precheck_fail", "quarantine", "skip"}
    if not args.include_done:
        candidates = [c for c in candidates
                      if c["id"] not in state["processed"]
                      or state["processed"][c["id"]]["status"] not in done_states]
        if args.verbose:
            print(f"排除 flywheel 终态后: {len(candidates)} 本", file=sys.stderr)

    # 排除 DB 已完整入库
    ingested = await _ingested_set(candidates)
    if not args.include_done:
        candidates = [c for c in candidates if c["id"] not in ingested]
        if args.verbose:
            print(f"排除 DB 已入库后: {len(candidates)} 本", file=sys.stderr)

    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]

    lines = [f"{c['md_path']}|{c['id']}|{c['title']}" for c in candidates]

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"书单已写 → {args.out} ({len(lines)} 本)", file=sys.stderr)
    else:
        for line in lines:
            print(line)


if __name__ == "__main__":
    asyncio.run(main())
