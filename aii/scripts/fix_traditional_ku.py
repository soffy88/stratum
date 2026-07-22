"""一次性修复: 已入库 KU 的繁体中文 → 简体(机械转换, OpenCC, 非LLM改写).
背景: _synth 是0LLM程序抠原文, 对繁体源书抠出的就是繁体; 旧存储逻辑
natural_text=en_or_zh 又把这份(繁体)中文误填进本该放独立英文的 natural_text 字段.
本脚本: 对含繁体字符的 natural_text_zh 转简体; 若原 natural_text 与 natural_text_zh
相同(旧 fallback 产生的重复, 非独立英文), 同步更新为转换后的简体, 保持"两者相同=
非真双语"这一前端判断信号成立.
用法: python scripts/fix_traditional_ku.py [--dry-run]
"""

import asyncio, os, re, sys

import asyncpg
import opencc
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

DSN = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
DRY_RUN = "--dry-run" in sys.argv
T2S = opencc.OpenCC("t2s")
_TRAD_HINT = re.compile(r"[經學個裡這對來說時們業實現後]")


async def main():
    conn = await asyncpg.connect(DSN)
    rows = await conn.fetch(
        "SELECT ku_id, natural_text, natural_text_zh FROM aii.ku_onto WHERE natural_text_zh ~ $1",
        _TRAD_HINT.pattern,
    )
    print(f"待修复 KU 数: {len(rows)}")
    fixed = 0
    for r in rows:
        zh_new = T2S.convert(r["natural_text_zh"])
        # 旧 fallback(natural_text==natural_text_zh, 非独立英文) → 同步转; 否则 natural_text 不动
        text_new = zh_new if r["natural_text"] == r["natural_text_zh"] else r["natural_text"]
        if zh_new == r["natural_text_zh"] and text_new == r["natural_text"]:
            continue  # 无实际变化(不应发生, 防御)
        if not DRY_RUN:
            await conn.execute(
                "UPDATE aii.ku_onto SET natural_text_zh=$1, natural_text=$2 WHERE ku_id=$3",
                zh_new,
                text_new,
                r["ku_id"],
            )
        fixed += 1
        if fixed <= 5:
            print(f"  [{r['ku_id']}] {r['natural_text_zh'][:40]} → {zh_new[:40]}")
    print(f"{'(DRY RUN, 未写入) ' if DRY_RUN else ''}已修复: {fixed}/{len(rows)}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
