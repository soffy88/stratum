"""批量回填 aii.ku_onto 里缺中文翻译的英文KU(natural_text_zh)。

背景(2026-07-25): 全库2994条可见(is_quarantined=false)、纯英文源、
natural_text_zh为空的KU——之前ku_translate.py管线指向的qwen3.5:9b模型
本机从未安装，大概率从写完就没跑起来过。已修模型指向qwen3-8b(实测约
0.4s/条,热身后), 本脚本做批量回填, 逐条UPDATE(非攒批量提交), 可随时
Ctrl-C中断安全恢复(下次重跑只会捞剩余空natural_text_zh的行)。

Usage:
  python3 aii/scripts/backfill_ku_translation.py                # 全量
  python3 aii/scripts/backfill_ku_translation.py --limit 50     # 先跑小批量试
"""

import argparse
import asyncio
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aii.service.ku_translate import translate_ku_to_zh

_FORMULA_RE = re.compile(r"\$[^$]+\$")


async def main(limit: int | None):
    import asyncpg

    conn = await asyncpg.connect(
        os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    )

    query = """
        SELECT ku_id, natural_text FROM aii.ku_onto
        WHERE is_quarantined = FALSE
          AND (natural_text_zh IS NULL OR natural_text_zh = '')
          AND natural_text !~ '[一-龥]'
          AND length(trim(natural_text)) > 0
        ORDER BY ku_id
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = await conn.fetch(query)
    total = len(rows)
    print(f"待翻译: {total} 条")

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
        if i % 50 == 0 or i == total:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"[{i}/{total}] ok={ok} fail={fail} 用时={elapsed:.0f}s 预计剩余={eta:.0f}s")

    print(f"\n完成: ok={ok} fail={fail} / {total}")
    await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    asyncio.run(main(args.limit))
