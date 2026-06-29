"""书内去重(防一本书内重复KU): 同 title 组内留最长, 删与之 embedding 余弦>阈值 的(同概念跨章重抽).
不碰同名但内容不同的(如数学 '定义1' 多个不同定义, 余弦低→保留). 用现成 embedding, 不重算.
用法: DATABASE_URL=... python scripts/dedup_within_book.py <substrate_id> [cos_threshold=0.80]
"""
import asyncio
import os
import sys

import asyncpg


async def dedup(sid: str, thr: float = 0.80) -> int:
    c = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        grps = await c.fetch(
            "SELECT title FROM aii.ku_onto WHERE substrate_id=$1 AND title IS NOT NULL "
            "GROUP BY title HAVING count(*)>1", sid)
        deleted = 0
        for g in grps:
            kus = await c.fetch(
                "SELECT ku_id, length(coalesce(natural_text_zh,natural_text,'')) ln, embedding "
                "FROM aii.ku_onto WHERE substrate_id=$1 AND title=$2 ORDER BY ln DESC", sid, g["title"])
            keep = kus[0]
            for k in kus[1:]:
                cos = await c.fetchval("SELECT 1-($1::vector<=>$2::vector)", keep["embedding"], k["embedding"])
                if cos and cos > thr:
                    await c.execute("DELETE FROM aii.ku_onto WHERE ku_id=$1", k["ku_id"])
                    deleted += 1
        print(f"[dedup] {sid}: 删书内重复 {deleted}")
        return deleted
    finally:
        await c.close()


if __name__ == "__main__":
    sid = sys.argv[1]
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.80
    asyncio.run(dedup(sid, thr))
