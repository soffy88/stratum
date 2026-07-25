"""隔离 aii.ku_onto 里已确认乱码的 KU(is_quarantined=true, 非删除, 可逆)。

背景(2026-07-25, "Group Chunks in Model Theory and Algebra"一案):
/ku/list 按 created_at DESC 排序且此前未过滤 is_quarantined, 导致最新一批
markitdown 转换失败(PDF内嵌数学字体(cid:N)字形泄漏 + 多栏排版被误判为表格
打碎陈述)的书刷屏占满前14页。math_corruption_gate.py 已补上这两个信号
(cid_leak/table_shred_row), 本脚本对已入库的 KU 行按同一套信号做一次性
回溯隔离, 而非删除(is_quarantined 可逆, DELETE 不可逆)。

判据(与 math_corruption_gate.py 的信号定义一致, 但直接对 DB 行而非整本MD判定,
因此更精细——只隔离真正命中信号的单条 KU, 而非把全书一刀切):
  - natural_text 含 "(cid:数字)" 字面量(cid_ratio 信号对照 15 本随机抽样样本
    全为 0, 零假阳性)
  - natural_text 命中打碎表格行模式, 且 substrate_id 属于 math_prog_*/advmath_*
    (限定这两个前缀家族: 2026-07-25 复核发现 econ_zh_*/misc_zh_* 也有零星命中,
    但 200 字前缀抽查未见明确证据、真假阳性未辨明, 保守不纳入本轮, 留独立复核)
  - natural_text 含 28+ 连续字母无空格(词间空格丢失), 且 substrate_id 属于
    math_prog_*/advmath_*——第一轮上线后发现 math_prog_2d236a001a 全书 291
    条 KU 里仍有 82 条(28%)未被前两个信号覆盖但逐条抽查确认同样是乱码,
    补第三信号后同一批复扫。同 table_shred, 限定这两个前缀家族——验证只在
    数学类书籍上做过(15本对照+1本追加), 未测过其它学科书里长英文/长URL/长
    化合物名等合法长串的假阳性率, 不确定前放宽范围, 跨学科全量应用留独立复核

Usage:
  python3 aii/scripts/quarantine_corrupted_ku.py           # dry-run, 只报数不落库
  python3 aii/scripts/quarantine_corrupted_ku.py --apply   # 实际执行 UPDATE
"""

import asyncio
import os
import sys

CID_COND = r"natural_text LIKE '%(cid:%'"
TABLE_SHRED_COND = (
    r"natural_text ~ '\| [^|]{1,20} \| [^|]{1,20} \|' "
    r"AND (substrate_id LIKE 'math_prog_%' OR substrate_id LIKE 'advmath_%')"
)
LONG_RUN_COND = (
    r"natural_text ~ '[A-Za-z]{28,}' "
    r"AND (substrate_id LIKE 'math_prog_%' OR substrate_id LIKE 'advmath_%')"
)
FULL_COND = f"({CID_COND}) OR ({TABLE_SHRED_COND}) OR ({LONG_RUN_COND})"


async def main(apply: bool):
    import asyncpg

    conn = await asyncpg.connect(
        os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    )

    already = await conn.fetchval(
        f"SELECT count(*) FROM aii.ku_onto WHERE ({FULL_COND}) AND is_quarantined = TRUE"
    )
    to_flag = await conn.fetchval(
        f"SELECT count(*) FROM aii.ku_onto WHERE ({FULL_COND}) AND is_quarantined = FALSE"
    )
    rows = await conn.fetch(
        f"""
        SELECT substrate_id, count(*) n
        FROM aii.ku_onto WHERE ({FULL_COND}) AND is_quarantined = FALSE
        GROUP BY substrate_id ORDER BY n DESC
        """
    )
    print(f"已隔离(跳过): {already}  待隔离: {to_flag}  涉及substrate: {len(rows)}")
    for r in rows:
        print(f"  {r['substrate_id']:30} {r['n']:>5}")

    if not apply:
        print("\n--dry-run(未落库)。加 --apply 实际执行 UPDATE。")
        await conn.close()
        return

    result = await conn.execute(
        f"UPDATE aii.ku_onto SET is_quarantined = TRUE, updated_at = now() "
        f"WHERE ({FULL_COND}) AND is_quarantined = FALSE"
    )
    print(f"\n已执行: {result}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
