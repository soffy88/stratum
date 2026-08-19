"""管道内翻译 — 合成后、质量门前, 为指定 substrate 的英文KU补中文译文(natural_text_zh).

★ 本脚本是飞轮管道的固定步骤, 不是手动回填.
用法: SUBSTRATE=econ_zh_abc123 python3 scripts/pipeline_translate_missing.py

背景: synthesize_book.py 的 LLM 有时只产出英文(EN+中文双语 prompt 不够强),
导致 natural_text_zh 为空 → 质量门双语率 0% → 隔离. 本步骤在合成后、
质量门前自动调用 Ollama(qwen3-8b, 本地)逐条翻译, 确保双语率达标.

退出码:
  0 = 翻译完成(含 0 条需翻译的情况)
  非 0 = 异常(不应阻断管道, 调用方用 || true)
"""

import asyncio
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aii.service.ku_translate import translate_ku_to_zh

_FORMULA_RE = re.compile(r"\$[^$]+\$")
SUBSTRATE = os.getenv("SUBSTRATE")
if not SUBSTRATE:
    print("❌ SUBSTRATE 未设置")
    sys.exit(1)


async def main():
    import asyncpg

    db_url = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    conn = await asyncpg.connect(db_url)

    rows = await conn.fetch(
        """
        SELECT ku_id, natural_text FROM aii.ku_onto
        WHERE substrate_id = $1
          AND (natural_text_zh IS NULL OR natural_text_zh = '')
          AND natural_text !~ '[一-龥]'
          AND length(trim(natural_text)) > 10
        ORDER BY ku_id
        """,
        SUBSTRATE,
    )
    total = len(rows)
    if total == 0:
        ku_count = await conn.fetchval(
            "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUBSTRATE
        )
        zh_count = await conn.fetchval(
            "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1 AND natural_text_zh ~ '[一-龥]'",
            SUBSTRATE,
        )
        print(f"  [翻译] 无需翻译: {zh_count}/{ku_count} KU 已有中文")
        await conn.close()
        return

    print(f"  [翻译] 待翻译: {total} 条英文KU")
    ok = fail = 0
    t0 = time.time()

    for i, r in enumerate(rows, 1):
        has_formula = bool(_FORMULA_RE.search(r["natural_text"]))
        zh = await asyncio.to_thread(translate_ku_to_zh, r["natural_text"], has_formula)
        if zh:
            await conn.execute(
                "UPDATE aii.ku_onto SET natural_text_zh = $1, updated_at = now() WHERE ku_id = $2",
                zh,
                r["ku_id"],
            )
            ok += 1
        else:
            fail += 1
        if i % 20 == 0 or i == total:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"  [翻译] [{i}/{total}] ok={ok} fail={fail} 剩余≈{eta:.0f}s")

    ku_count = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUBSTRATE
    )
    zh_count = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1 AND natural_text_zh ~ '[一-龥]'",
        SUBSTRATE,
    )
    bilingual_pct = round(100 * zh_count / max(ku_count, 1))
    print(f"  [翻译] 完成: ok={ok} fail={fail} → 双语率 {bilingual_pct}% ({zh_count}/{ku_count})")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
