#!/usr/bin/env python3
"""回填 math_prog 存量 KU 的 knowledge_type —— 纠正"静默默认值"造成的错分。

★这不是"改判", 是纠错:
  math_program_ingest 的 _TYPE_ZH 只映射【英文】标记(Example→例子), 中文书的
  "例"/"例题" 原样透传; 而 math_ingest._ku_type 的表里只有"例子" —— 于是中文书的
  例题全部落到 `.get(t, "conceptual")` 这个默认值, 被存成 conceptual。
  没有任何人判断过"这条例题是概念", 它只是掉进了默认分支。
  与 fail-open 同族: 落默认值不报警, 错误就能永久隐身。

★判据来源可审计, 不猜:
  ku_id 的构造是 `{substrate}::{chapter}::{point}`, 而 point 就是【书自带的标记】
  (定理 3.3.2 / 3.3 推论 4 / Theorem 3.2.3)。类型直接从 ku_id 第三段解析,
  不重读源 MD、不调 LLM、不依赖任何模型判断 —— 同一份输入永远得到同一个答案,
  改错了能按同一条规则改回来(可逆)。

★只动 knowledge_type 一个字段。KU 内容/title/命名一律不碰(红线: 不动存量 KU 写入)。

用法:
  uv run python scripts/backfill_math_ku_type.py --dry-run   # 出前后分布对比, 不写库
  uv run python scripts/backfill_math_ku_type.py             # 真写
"""

import argparse
import asyncio
import os
import re
import sys
from collections import Counter

import asyncpg

DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")

# 与 math_ingest._ku_type 保持同一张表(修复后的版本)
_TYPE_TO_KT = {
    "定理": "rationale",
    "推论": "rationale",
    "引理": "rationale",
    "命题": "rationale",
    "Theorem": "rationale",
    "Lemma": "rationale",
    "Proposition": "rationale",
    "Corollary": "rationale",
    "例子": "procedural",
    "例": "procedural",
    "例题": "procedural",
    "Example": "procedural",
    "定义": "conceptual",
    "知识点": "conceptual",
    "Definition": "conceptual",
}
# 从 point 里认标记词。中文"例题"要排在"例"前面(最长匹配优先), 否则"例题"会被"例"截胡。
_MARK = re.compile(
    r"(Definition|Theorem|Lemma|Proposition|Corollary|Example"
    r"|定义|定理|引理|推论|命题|例题|例)"
)


def type_of(ku_id: str) -> str | None:
    """从 ku_id 第三段(书自带标记)解析类型。解析不出返回 None —— 不硬猜。"""
    parts = ku_id.split("::")
    if len(parts) < 3:
        return None
    m = _MARK.search(parts[2])
    return m.group(1) if m else None


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT ku_id, knowledge_type FROM aii.ku_onto WHERE substrate_id LIKE 'math_prog%'"
        )
        before = Counter(r["knowledge_type"] for r in rows)
        changes, unparsed = [], 0
        after = Counter()
        for r in rows:
            t = type_of(r["ku_id"])
            if t is None:
                unparsed += 1
                after[r["knowledge_type"]] += 1  # 解析不出的保持原样, 不动
                continue
            kt = _TYPE_TO_KT[t]
            after[kt] += 1
            if kt != r["knowledge_type"]:
                changes.append((r["ku_id"], kt))

        print(f"math_prog 存量 KU {len(rows)} 条 | 标记解析不出 {unparsed} 条(保持原值, 不动)")
        print(f"\n{'类型':12s} {'回填前':>8s} {'回填后':>8s}  {'差':>7s}")
        for kt in ("conceptual", "rationale", "procedural"):
            d = after[kt] - before[kt]
            print(f"{kt:12s} {before[kt]:8d} {after[kt]:8d}  {d:+7d}")
        print(f"\n需要改动 {len(changes)} 条 = {100 * len(changes) / max(len(rows), 1):.1f}%")

        if args.dry_run:
            print("\n[dry-run] 未写库。样例(前8条):")
            for k, kt in changes[:8]:
                print(f"   {k[:58]:60s} → {kt}")
            return 0

        async with conn.transaction():
            await conn.executemany(
                "UPDATE aii.ku_onto SET knowledge_type=$2, updated_at=now() WHERE ku_id=$1",
                changes,
            )
        print(f"\n✅ 已回填 {len(changes)} 条 knowledge_type(仅此一个字段)")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
