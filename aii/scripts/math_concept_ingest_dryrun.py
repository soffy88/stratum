#!/usr/bin/env python3
"""staging 的 concept_candidate=True → aii.concept_onto(全部 grade=candidate)。

★这是【入库工序】, 与命名工序(math_prog_rename_batch)刻意分开走 —— 命名错了不污染
概念层。默认 dry-run, --apply 才写库。

入库三道闸(依次):
  闸1 结构闸: 只收 concept_candidate=True(定理/定义/引理/推论/命题)。
      例题的"名"是这道题的摘要不是概念(实测: 拆差分解极限/导数差商极限), 冒充概念就是编。
  闸2 名字过滤(复用 math_program_ingest._is_name 同一把尺, 实测双向修过):
      拦裸记号(S n / X j / Fn)、Unicode 记号(Ω,𝒜,ℙ)、形容词(real-valued/nonparametric);
      豁免 en-dash 与重音字母 —— 数学最经典的人名定理都带(Borel–Cantelli/Berry–Esséen),
      老过滤器把它们当垃圾拦了, 误杀比漏拦更疼(真金拦在门外且无人知晓)。
  闸3 去重: 同名(归一后)只落一个概念, 多本书贡献同一概念 → 记多来源不重复建。

★全部 grade='candidate', 不是 confirmed:
  实测 ② 的编造率约 8%(样本12条中1条: "Dimension as Number of Bases" 数学上就是错的
  —— 维数是基的大小不是基的个数)。这种错读起来像模像样、checker 发现不了、只有懂数学
  的人能看出 —— 正是原则二的教科书情形: 没有不能撒谎的自动裁判 → 留人。
  candidate 层不参与自动合并, 编造的概念到不了 confirmed, 只是躺着等确认或交叉印证。

用法:
  uv run python scripts/math_concept_ingest_dryrun.py                 # dry-run 出报告
  uv run python scripts/math_concept_ingest_dryrun.py --apply         # 真写
  uv run python scripts/math_concept_ingest_dryrun.py --staging DIR   # 指定 staging 根
"""

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import asyncpg

DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
DEFAULT_STAGING = Path("scripts/_staging/math_prog_rename")

# ── 闸2: 与 math_program_ingest 同一把尺(复制而非 import: 那个脚本模块级读 sys.argv) ──
_NAME_OK = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ,.\-‐-―'’&]+$")
_BARE_NOTATION = re.compile(r"^[A-Za-z][A-Za-z]?\s*[a-z0-9]?$")
_NAME_OK_ZH = re.compile(r"^[一-鿿A-Za-z0-9，,、·（）()《》\-\s]{2,45}$")


def is_name(s: str) -> bool:
    s = (s or "").strip()
    if len(s) < 3:
        return False
    if _BARE_NOTATION.match(s):
        return False
    if _NAME_OK.match(s):
        return s[0].isupper() or " " in s
    return bool(_NAME_OK_ZH.match(s) and re.search(r"[一-鿿]", s))


def norm(s: str) -> str:
    """去重键: 大小写/空白/首尾标点归一。不做词干/单复数 —— 宁碎片不错合。"""
    return re.sub(r"\s+", " ", (s or "").strip().lower()).strip(" .,;:·")


def collect(staging_root: Path):
    """扫 staging, 返回 (通过三道闸的概念, 各闸淘汰计数)。"""
    stats = Counter()
    by_norm: dict[str, dict] = {}
    for sub_dir in sorted(staging_root.glob("*/")):
        sub = sub_dir.name
        for f in sorted(sub_dir.glob("ch*.json")):
            try:
                items = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                stats["读取失败章"] += 1
                continue
            for it in items:
                stats["staging总条数"] += 1
                if not it.get("concept_candidate"):
                    stats["闸1_非概念类(例题等)"] += 1
                    continue
                nm = (it.get("llm_name") or "").strip()
                if not nm:
                    stats["闸1_无名字"] += 1
                    continue
                if not is_name(nm):
                    stats["闸2_名字被过滤"] += 1
                    continue
                k = norm(nm)
                if k in by_norm:
                    stats["闸3_重复(并入来源)"] += 1
                    by_norm[k]["sources"].add(sub)
                    continue
                by_norm[k] = {"name": nm, "type": it.get("type"), "sources": {sub}}
                stats["通过_新概念"] += 1
    return by_norm, stats


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", default=str(DEFAULT_STAGING))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root = Path(args.staging)
    if not root.exists():
        print(f"staging 不存在: {root}", file=sys.stderr)
        return 1
    by_norm, stats = collect(root)

    print(f"扫描 {root}")
    for k in (
        "staging总条数",
        "闸1_非概念类(例题等)",
        "闸1_无名字",
        "闸2_名字被过滤",
        "闸3_重复(并入来源)",
        "通过_新概念",
        "读取失败章",
    ):
        if stats.get(k):
            print(f"  {k:24s} {stats[k]:6d}")
    print(f"\n按 KU 类型: {dict(Counter(v['type'] for v in by_norm.values()))}")

    conn = await asyncpg.connect(DSN)
    try:
        names = [v["name"] for v in by_norm.values()]
        exist = set()
        if names:
            rows = await conn.fetch(
                "SELECT name FROM aii.concept_onto WHERE lower(name) = ANY($1::text[])",
                [norm(n) for n in names],
            )
            exist = {norm(r["name"]) for r in rows}
        fresh = [v for k, v in by_norm.items() if k not in exist]
        print(f"\n库中已存在(跳过) {len(by_norm) - len(fresh)} | 将新建 {len(fresh)}")
        print("\n样例(前15条, 均将落 grade=candidate):")
        for v in fresh[:15]:
            print(f"   [{v['type']:3s}] {v['name'][:44]:46s} 来源{len(v['sources'])}本")

        if not args.apply:
            print("\n[dry-run] 未写库。--apply 才落库。")
            return 0

        # 真写: 全部 grade=candidate。discipline 整桶=数学(math_prog 已定)。
        async with conn.transaction():
            for v in fresh:
                await conn.execute(
                    "INSERT INTO aii.concept_onto(name, discipline, grade) VALUES($1,'数学','candidate') "
                    "ON CONFLICT (name) DO NOTHING",
                    v["name"],
                )
        print(f"\n✅ 落库 {len(fresh)} 个概念(grade=candidate, discipline=数学)")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
