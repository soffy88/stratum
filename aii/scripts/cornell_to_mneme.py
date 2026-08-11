#!/usr/bin/env python3
"""stratum 康奈尔生成器 → mneme 交互式康奈尔内容包。

两项目同源设计(stratum=生成端, mneme=交互学习端):
  stratum.cornell_notes.content {topicId,version,subject,title,cues,modules,summary,oneLiner}
  → mneme data/cornell_topics/{topicId}/content.json(最小契约完全命中)

mneme 前端获得自动生成的康奈尔卡 → 交互回忆(线索提问→闭卷→对照→自报进度)。

用法:
    .venv/bin/python scripts/cornell_to_mneme.py [--out /data/soffy/projects/mneme/data/cornell_topics]
    [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import asyncpg

AII_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
DEFAULT_OUT = Path("/data/soffy/projects/mneme/data/cornell_topics")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(AII_URL)
    rows = await conn.fetch(
        "SELECT topic_id, title, subject, content FROM stratum.cornell_notes"
        " WHERE source='machine' AND deleted_at IS NULL ORDER BY created_at")
    await conn.close()
    print(f"康奈尔卡片: {len(rows)} 张", flush=True)

    out_root = Path(args.out)
    written = skipped = 0
    for r in rows:
        cj = r["content"]
        if isinstance(cj, str):
            cj = json.loads(cj)
        # 最小契约字段校验(缺关键字段跳过)
        need = ("topicId", "version", "subject", "title", "cues", "modules", "summary")
        if not all(k in cj for k in need):
            print(f"  ⚠ 跳过(缺字段): {r['topic_id']}", flush=True)
            skipped += 1
            continue
        topic_id = re.sub(r"[^a-zA-Z0-9_-]", "-", cj["topicId"] or r["topic_id"])
        # 目录名与 content.topicId 保持一致(mneme 测试断言二者相等)
        if cj.get("topicId") != topic_id:
            cj["topicId"] = topic_id
        if args.dry_run:
            print(f"[dry] {topic_id}: {cj['title'][:30]} | {len(cj['cues'])} cues"
                  f" | {len(cj['modules'])} modules")
            written += 1
            continue
        pkg = out_root / topic_id
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "content.json").write_text(
            json.dumps(cj, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
    print(f"完成: {written} 张导出 → {out_root} ({'DRY-RUN' if args.dry_run else '已写入'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
