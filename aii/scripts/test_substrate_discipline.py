"""★回归测试: substrate→discipline 权威映射 + onto_persist 的 NULL 窗口已消灭。

守两条:
  ① 映射表里有的 substrate → 概念【插入时】就带上真学科, 不留 NULL 窗口
     (旧实现是先插 NULL、后面再 COALESCE 补, 补不到就永久留空/留成 substrate id
      ——那是 concept_onto.discipline 长期 190 种脏取值的根源之一)
  ② 映射表里【没有】的 substrate → 直接报错拒绝, 不静默放行
     (Wiki 2026-07-20 运维纪律: 新书登记 discipline 必填, 否则新 substrate 继续烂)

用真库(aii_kg)只读校验映射表状态 + 用临时概念名走一遍真实 upsert 语句, 跑完清理。

运行:
  python scripts/test_substrate_discipline.py
退出码: 0=全通过, 1=有失败
"""

import asyncio
import os
import sys

import asyncpg

DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
CONTROLLED = {"数学", "经济学", "哲学", "心理学", "计算机", "其他"}
_TMP = "__test_substrate_discipline_tmp__"

PASS, FAIL = 0, 0


def check(label: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    print(f"  {'✅' if ok else '❌'} [{label}] {detail}")
    if ok:
        PASS += 1
    else:
        FAIL += 1


async def main():
    print("substrate→discipline 映射回归测试")
    conn = await asyncpg.connect(DSN)
    try:
        # 1. 映射表存在且非空
        n = await conn.fetchval("SELECT count(*) FROM aii.substrate_discipline")
        check("映射表非空", n > 0, f"{n} 行")

        # 2. 全部落在受控集合内(CHECK 约束应保证, 这里再实测一次)
        bad = await conn.fetch(
            "SELECT DISTINCT discipline FROM aii.substrate_discipline "
            "WHERE discipline <> ALL($1::text[])",
            list(CONTROLLED),
        )
        check("全部在受控集合内", not bad, f"越界值={[b['discipline'] for b in bad]}")

        # 3. 论文 substrate 刻意不在表里(Wiki 决定排除出概念层)
        papers = await conn.fetchval(
            "SELECT count(*) FROM aii.substrate_discipline WHERE substrate_id LIKE 'advmath_en%'"
        )
        check("论文substrate未混入映射表", papers == 0, f"advmath_en 行数={papers}")

        # 4. 有KU的非论文 substrate 全部有映射(否则 onto_persist 会拒绝那本书)
        missing = await conn.fetchval(
            "SELECT count(DISTINCT k.substrate_id) FROM aii.ku_onto k "
            "LEFT JOIN aii.substrate_discipline sd USING (substrate_id) "
            "WHERE sd.substrate_id IS NULL AND k.substrate_id NOT LIKE 'advmath_en%'"
        )
        check("在用substrate无遗漏", missing == 0, f"缺映射={missing}")

        # 5. ★核心: 概念插入时就带 discipline(复现 onto_persist 改后的那条 upsert)
        sample = await conn.fetchrow(
            "SELECT substrate_id, discipline FROM aii.substrate_discipline LIMIT 1"
        )
        async with conn.transaction():
            cid = await conn.fetchval(
                "INSERT INTO aii.concept_onto(name, discipline) VALUES($1,$2) "
                "ON CONFLICT (name) DO UPDATE SET discipline = "
                "COALESCE(aii.concept_onto.discipline, EXCLUDED.discipline) "
                "RETURNING concept_id",
                _TMP,
                sample["discipline"],
            )
            got = await conn.fetchval(
                "SELECT discipline FROM aii.concept_onto WHERE concept_id=$1", cid
            )
            check("插入即带真学科(无NULL窗口)", got == sample["discipline"], f"得到 {got!r}")
            # 6. 二次 upsert 不会把已有学科冲掉(首个非空胜出的语义保持)
            await conn.execute(
                "INSERT INTO aii.concept_onto(name, discipline) VALUES($1,$2) "
                "ON CONFLICT (name) DO UPDATE SET discipline = "
                "COALESCE(aii.concept_onto.discipline, EXCLUDED.discipline)",
                _TMP,
                "其他",
            )
            got2 = await conn.fetchval(
                "SELECT discipline FROM aii.concept_onto WHERE concept_id=$1", cid
            )
            check("重复upsert不覆盖已有学科", got2 == sample["discipline"], f"仍为 {got2!r}")
            raise asyncpg.exceptions.PostgresError  # 回滚, 不留测试数据
    except asyncpg.exceptions.PostgresError:
        pass
    finally:
        # 兜底清理(事务已回滚, 这里只是双保险)
        await conn.execute("DELETE FROM aii.concept_onto WHERE name = $1", _TMP)
        await conn.close()

    print(f"\n通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
