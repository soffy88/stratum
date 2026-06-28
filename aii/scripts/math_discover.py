"""发现未处理的数学类书籍并输出书单.

用途: 供 math_flywheel.sh 调用, 生成当次要处理的书单文件.

算法:
  1. 扫 /home/soffy/shared/stratum-to-aii/*.json (sidecar)
  2. 过滤 medium==book + 数学关键词
  3. 按标题去重 (同标题取 id 最小/最早的那条)
  4. 从 flywheel_state.json 排除已终态(ingested/precheck_fail/quarantine)
  5. 从 DB 排除已完整入库 (ku_onto KU数>30 且 ingested_substrate 已登记)
  6. 输出 `md绝对路径|substrate_id|书名` 格式的书单

Usage:
  python scripts/math_discover.py [--out /path/to/list.txt] [--limit N]
"""
import asyncio, asyncpg, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

STRATUM_DIR = Path("/home/soffy/shared/stratum-to-aii")
STATE_FILE = ROOT / "math_pipeline" / "flywheel_state.json"

MATH_KEYWORDS = [
    "数学", "高等数学", "数学分析", "线性代数", "概率论", "微积分",
    "calculus", "algebra", "analysis", "probability", "statistics",
    "geometry", "代数", "几何", "拓扑", "统计学", "运筹",
    "数值分析", "复变函数", "实变函数", "泛函分析", "微分方程",
    "常微分", "偏微分", "离散数学", "组合数学", "数论",
    "矩阵", "向量空间", "级数", "积分", "导数",
]

SKIP_KEYWORDS = [
    "数学教你", "数学家的", "哲学", "philosophy", "psychology", "心理",
    "技术大全", "经济", "管理", "金融", "finance", "economic",
    "manipulation", "德国一流大学",
]


def _is_math(title: str) -> bool:
    t = title.lower()
    if any(k.lower() in t for k in SKIP_KEYWORDS):
        return False
    return any(k.lower() in t for k in MATH_KEYWORDS)


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"processed": {}}


def discover_candidates() -> list[dict]:
    """返回 [{id, title, md_path}] 列表(已去重/已过滤学科)."""
    by_title: dict[str, dict] = {}
    for f in sorted(STRATUM_DIR.glob("*.json")):
        if f.stem.endswith("_structured") or ".sidecar" in f.name:
            continue
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("medium") != "book":
            continue
        title = meta.get("title") or ""
        if not _is_math(title):
            continue
        sid = meta["id"]
        # 优先 _structured.md(Stratum重出的规范版)
        structured_md = STRATUM_DIR / (sid + "_structured.md")
        original_md = STRATUM_DIR / (sid + ".md")
        if structured_md.exists():
            md_path = structured_md
        elif original_md.exists():
            md_path = original_md
        else:
            continue
        if title not in by_title or sid < by_title[title]["id"]:
            by_title[title] = {"id": sid, "title": title, "md_path": str(md_path)}
    return list(by_title.values())


async def _ingested_set(candidates: list[dict]) -> set[str]:
    """从 DB 查已完整入库 (ku_onto KU数>30 且 ingested_substrate 已登记)."""
    ids = [c["id"] for c in candidates]
    if not ids:
        return set()
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("""
        SELECT substrate_id
        FROM aii.ingested_substrate
        WHERE substrate_id = ANY($1::text[])
          AND ku_count > 30
          AND subject = '数学'
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
        print(f"扫描数学书候选: {len(candidates)} 本 (去重后)", file=sys.stderr)

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
