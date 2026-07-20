"""一次性回填 rf.refined_kc_concept — 给 0005 迁移【之前】固化的主题KC 补上概念归属。

背景: build_theme_kc.py 早先只写了 KU 成员(refined_kc_member), 概念归属没存。
/api/graph/themes 于是靠"每次重跑 Leiden + 按 size 位置对齐 kc_id"来染色, 图一变
就静默错位(见 migrations/refined/0005_kc_concept_member.sql)。0005 之后固化的会直接
写 refined_kc_concept, 但已有的旧主题需要补。

★这个脚本【复现】的正是那套位置对齐——所以它只在"概念图自固化以来完全没变"时才
成立。变了就没法可信回填(对齐本身就是错的), 那时唯一诚实的做法是重跑 build_theme_kc.py
重新聚类+命名, 而不是让脚本猜。因此下面三道硬闸, 任何一道不过就中止, 不写半个字节:
  ① 固化后有新增概念/新增边 → 中止
  ② 重算出的 cluster 数 != 当前版主题行数 → 中止
  ③ 目标主题已经有概念成员 → 中止(不重复写, 不覆盖)

用法:
  uv run python scripts/backfill_kc_concept.py --dry-run   # 只看会写什么
  uv run python scripts/backfill_kc_concept.py             # 真写
退出码: 0=成功或无事可做, 1=闸门拦下(需人工判断)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_theme_kc import _build_partition  # noqa: E402  ★共用同一套图构建+seed

REFINED_DSN = os.getenv(
    "REFINED_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined"
)

# 跟 build_theme_kc.py 的默认值一致——回填必须复现固化当时的参数, 不能换。
_RESOLUTION = 1.0
_MIN_SIZE = 3


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(REFINED_DSN)
    try:
        themes = await conn.fetch(
            "SELECT kc_id, theme_name, created_at FROM rf.refined_theme_kc "
            "WHERE is_current = true ORDER BY kc_id"
        )
        if not themes:
            print("没有当前版主题KC, 无事可做。")
            return 0

        fixed_at = max(r["created_at"] for r in themes if r["created_at"])

        # 闸①: 图变过就不能用位置对齐回填
        n_new_c = await conn.fetchval(
            "SELECT count(*) FROM rf.refined_concept WHERE created_at > $1", fixed_at
        )
        n_new_e = await conn.fetchval(
            "SELECT count(*) FROM rf.refined_directed_edge WHERE created_at > $1", fixed_at
        )
        if n_new_c or n_new_e:
            print(
                f"❌ 中止: 固化({fixed_at})后概念图已变化(新增 {n_new_c} 概念 / {n_new_e} 边)。\n"
                "   位置对齐不再可信, 回填会写入错误归属。请改为重跑 scripts/build_theme_kc.py "
                "重新聚类+命名。",
                file=sys.stderr,
            )
            return 1

        # 闸③: 已有概念成员就不动
        existing = await conn.fetchval(
            "SELECT count(*) FROM rf.refined_kc_concept WHERE kc_id = ANY($1::bigint[])",
            [r["kc_id"] for r in themes],
        )
        if existing:
            print(f"当前版主题已有 {existing} 条概念成员, 无需回填(不覆盖)。")
            return 0

        concepts = await conn.fetch(
            "SELECT concept_id, name, name_zh, discipline FROM rf.refined_concept"
        )
        edges = await conn.fetch(
            "SELECT src_concept, dst_concept, strength FROM rf.refined_directed_edge"
        )
        id_list, partition = _build_partition(concepts, edges, _RESOLUTION)

        clusters = [[id_list[i] for i in m] for m in partition if len(m) >= _MIN_SIZE]
        clusters.sort(key=len, reverse=True)

        # 闸②: 数量对不上说明复现失败
        if len(clusters) != len(themes):
            print(
                f"❌ 中止: 重算得到 {len(clusters)} 个社区, 但当前版有 {len(themes)} 个主题KC, "
                "对不上——无法可信对齐。请重跑 scripts/build_theme_kc.py。",
                file=sys.stderr,
            )
            return 1

        rows = [(themes[i]["kc_id"], cid) for i, cl in enumerate(clusters) for cid in cl]
        by_id = {c["concept_id"]: c for c in concepts}
        for i, cl in enumerate(clusters):
            names = [by_id[m]["name_zh"] or by_id[m]["name"] for m in cl][:5]
            print(
                f"  kc_id={themes[i]['kc_id']} 【{themes[i]['theme_name']}】{len(cl)}概念: {names}"
            )

        if args.dry_run:
            print(f"\n[dry-run] 将写入 {len(rows)} 条 (kc_id, concept_id), 未写库。")
            return 0

        await conn.executemany(
            "INSERT INTO rf.refined_kc_concept (kc_id, concept_id) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            rows,
        )
        print(f"\n✅ 回填完成: {len(rows)} 条概念归属 → rf.refined_kc_concept")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
