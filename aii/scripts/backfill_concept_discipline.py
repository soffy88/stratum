#!/usr/bin/env python3
"""回填 aii.concept_onto.discipline —— 从 aii.substrate_discipline 权威映射反推。

背景: concept_onto.discipline 长期是脏的(190 种取值, 大部分是 per-book substrate id、
中英文同义并存、空值), 导致一切按学科的判断失真。权威映射已落 aii.substrate_discipline
(见 migrations/0002 + seed/substrate_discipline.tsv)。本脚本把它反推到概念上。

判据: 一个概念的学科 = 它的 KU 来自哪些 substrate 的【多数决】(按 KU 条数),
      平票时按学科名排序取第一个(确定性, 可重放)。

★三类概念不回填, 各有理由, 不硬凑:
  ① 只有论文(advmath_en)KU 的 —— Wiki 已决定论文排除出概念层, 它们本就不该有学科
  ② 无任何 KU 链接的孤儿概念 —— 无从判断(2026-07-20 实测 9336 个, 占 53%;
     来源是 onto_persist 把"KU 里提到的所有名字"都插了概念表, 另案)
  ③ substrate 不在映射表里的 —— 报出来等人补映射, 不猜

幂等: 可重复跑。用法:
  uv run python scripts/backfill_concept_discipline.py --dry-run
  uv run python scripts/backfill_concept_discipline.py
"""

import argparse
import asyncio
import os

import asyncpg

DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")

# 多数决: 按 KU 条数排序, 平票按学科名(确定性)
_VOTE_SQL = """
WITH cd AS (
  SELECT kc.concept_id, sd.discipline, count(*) AS n
  FROM aii.ku_concept_onto kc
  JOIN aii.ku_onto k ON k.ku_id = kc.ku_id
  JOIN aii.substrate_discipline sd ON sd.substrate_id = k.substrate_id
  GROUP BY 1, 2
), rk AS (
  SELECT concept_id, discipline,
         row_number() OVER (PARTITION BY concept_id ORDER BY n DESC, discipline) AS rn
  FROM cd
)
SELECT concept_id, discipline FROM rk WHERE rn = 1
"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(DSN)
    try:
        total = await conn.fetchval("SELECT count(*) FROM aii.concept_onto")
        votes = await conn.fetch(_VOTE_SQL)
        orphan = await conn.fetchval(
            "SELECT count(*) FROM aii.concept_onto c WHERE NOT EXISTS "
            "(SELECT 1 FROM aii.ku_concept_onto kc WHERE kc.concept_id = c.concept_id)"
        )
        # substrate 有 KU 但不在映射表 → 需要人补, 不猜
        unmapped = await conn.fetch(
            "SELECT DISTINCT k.substrate_id FROM aii.ku_onto k "
            "LEFT JOIN aii.substrate_discipline sd USING (substrate_id) "
            "WHERE sd.substrate_id IS NULL AND k.substrate_id NOT LIKE 'advmath_en%' "
            "ORDER BY 1"
        )

        print(f"概念总数 {total} | 可回填 {len(votes)} | 无KU孤儿 {orphan}")
        if unmapped:
            print(f"⚠️ {len(unmapped)} 个 substrate 有KU但不在映射表(未回填, 待人补映射):")
            for r in unmapped[:10]:
                print(f"   {r['substrate_id']}")
        if args.dry_run:
            print("\n[dry-run] 未写库。")
            return 0

        async with conn.transaction():
            await conn.executemany(
                "UPDATE aii.concept_onto SET discipline = $2 WHERE concept_id = $1",
                [(r["concept_id"], r["discipline"]) for r in votes],
            )
            # 第2遍: 孤儿概念(无KU, 上面投不到票)里, 有一批 discipline 的【值本身就是
            # substrate_id】(materialize_links.py 当年直接写的 SUB)。直接查映射表换成真
            # 学科——这不是猜, 是同一张权威表的另一种命中方式。
            n_sub = await conn.execute(
                "UPDATE aii.concept_onto c SET discipline = sd.discipline "
                "FROM aii.substrate_discipline sd WHERE sd.substrate_id = c.discipline"
            )
            # 第3遍: 中英文/大小写异写归一到受控集合。纯字面同义, 无判断成分。
            n_alias = await conn.execute(
                "UPDATE aii.concept_onto SET discipline = CASE lower(discipline) "
                "  WHEN 'economics' THEN '经济学' WHEN 'econ' THEN '经济学' "
                "  WHEN 'math' THEN '数学' WHEN 'mathematics' THEN '数学' "
                "  WHEN 'philosophy' THEN '哲学' WHEN 'psychology' THEN '心理学' END "
                "WHERE lower(discipline) = ANY (ARRAY['economics','econ','math','mathematics','philosophy','psychology'])"
            )
        print(f"\n✅ 多数决回填 {len(votes)} 个概念")
        print(f"   孤儿概念按 substrate 值直查映射表: {n_sub}")
        print(f"   中英文异写归一: {n_alias}")
        for r in await conn.fetch(
            "SELECT discipline, count(*) n FROM aii.concept_onto GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ):
            print(f"   {r['discipline'] or '(NULL)'}: {r['n']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
