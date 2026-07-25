"""清空 advmath 讲透管线遗留的"标签残片"natural_text(2026-07-25一案)。

synthesize_book_advmath.py::_split_bilingual 此前把双语LLM输出里孤立的英文
小节标题行("Source:"/"Gloss:"/"Notes:"等, 不含CJK)误判成整段"英文正文",
真内容全在 natural_text_zh 里。embedding 计算用的是 `zh or en`(已优先zh,
未受影响), 但展示层 natural_text 是纯标签残片。已在 synthesize_book_advmath.py
修好 split 逻辑(未来新抽取不再产生此问题); 本脚本只清理已入库的历史行——
natural_text 设为空串(与全书本为中文源、natural_text_zh 留空的对称语义一致:
"该语言无有效内容"), 不删除整条 KU(zh 内容完好, 检索/展示不受影响)。

Usage:
  python3 aii/scripts/fix_stub_natural_text.py           # dry-run
  python3 aii/scripts/fix_stub_natural_text.py --apply
"""

import asyncio
import os
import sys

# 与 synthesize_book_advmath.py::_LABEL_ONLY 同一判据, 只挑 natural_text 本身
# 是"纯标签残片"且 natural_text_zh 确有实质内容(>=10个中文字符)的行。
STUB_COND = r"""
    natural_text ~ '^[A-Za-z][A-Za-z \-'']{0,25}[:.]?$'
    AND length(regexp_replace(coalesce(natural_text_zh,''), '[^一-龥]', '', 'g')) >= 10
"""

# 人工逐条核对29条命中(2026-07-25): 28条确系残片(Source:/Gloss:/Notes:/
# Glossary.../Citation/References/Fantastic/END/SOLUTION:/Math:等), 唯一例外
# econ_zh_da27a19f30::ch3_ku2 = "Comparative Advantage"(比较优势)是真实
# 概念名不是残片标签, 显式排除、不清空。
_EXCLUDE_KU_IDS = {"econ_zh_da27a19f30::ch3_ku2"}


async def main(apply: bool):
    import asyncpg

    conn = await asyncpg.connect(
        os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    )
    all_rows = await conn.fetch(
        f"SELECT ku_id, substrate_id, natural_text FROM aii.ku_onto WHERE {STUB_COND}"
    )
    rows = [r for r in all_rows if r["ku_id"] not in _EXCLUDE_KU_IDS]
    print(f"命中: {len(all_rows)}  排除: {len(all_rows) - len(rows)}  待清空: {len(rows)}")
    for r in rows:
        print(f"  {r['ku_id']:40} natural_text={r['natural_text']!r}")

    if not apply:
        print("\n--dry-run(未落库)。加 --apply 实际执行 UPDATE。")
        await conn.close()
        return

    ids = [r["ku_id"] for r in rows]
    result = await conn.execute(
        "UPDATE aii.ku_onto SET natural_text = '', updated_at = now() WHERE ku_id = ANY($1::text[])",
        ids,
    )
    print(f"\n已执行: {result}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
