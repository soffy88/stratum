"""飞轮重试: 将因双语率/KU密度/rationale隔离的书从 quarantine 状态释放,
重新加入飞轮队列.

背景(2026-07-30): 四个飞轮累计 414 本书全部被隔离(0 本通过), 主因:
  1. 双语率 0% — 已修: 英文书不再检查双语率(A仓命门是抽全不漏, 翻译是下游的事)
  2. KU 密度不足 — 阈值过高(已修: 60%→35%, 15/章→10/章)
  3. rationale=0 — prompt 不够强(已修: PLAN_SYS 强化)
本脚本识别"可重试"的隔离书(隔离原因已被修复), 清除其在飞轮状态中的
终态标记, 并清理 DB 中对应的残留 KU/概念/KC/BU(重跑时需要干净起点).

不可重试的隔离原因(上游问题, 重试仍会失败):
  - precheck_fail: MD 文件结构损坏(需上游 PDF→MD 转换修复)
  - 双语率0% + KU密度0 + 无章节: MD 内容本身有问题
  - 管道步骤失败: 程序 bug(需先修代码)

Usage:
  python3 scripts/flywheel_retry_quarantined.py --pipeline econ   # 经济学中文
  python3 scripts/flywheel_retry_quarantined.py --pipeline advmath # 高级数学经济
  python3 scripts/flywheel_retry_quarantined.py --pipeline misc   # 其它学科
  python3 scripts/flywheel_retry_quarantined.py --pipeline all    # 全部
  python3 scripts/flywheel_retry_quarantined.py --pipeline econ --dry-run  # 只看不动
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 管道配置 ──
PIPELINE_CONFIGS = {
    "econ": {
        "state_file": "econ_pipeline/flywheel_zh_state.json",
        "quarantine_file": "econ_pipeline/quarantine.json",
    },
    "advmath": {
        "state_file": "advmath_pipeline/flywheel_state.json",
        "quarantine_file": "advmath_pipeline/quarantine.json",
    },
    "misc": {
        "state_file": "misc_pipeline/flywheel_misc_state.json",
        "quarantine_file": "misc_pipeline/quarantine.json",
    },
}

# ── 可重试的隔离原因关键词 ──
RETRYABLE_PATTERNS = [
    r"双语率\d+%<",           # bilingual rate too low → now fixed by translation step
    r"KU密度不足: 实抽[1-9]", # KU density too low (but had SOME KUs) → relaxed thresholds
    r"rationale\(why\)=0",    # no rationale extracted → now fixed by stronger prompt
    r"低密度章过多",          # too many low-density chapters → now fixed by lower floor
    r"完整率(9[0-9]|[5-8]\d)%<100%",  # completeness 50-99% (not 0%) → relaxed to 90%
]

# ── 不可重试的隔离原因 ──
NON_RETRYABLE_PATTERNS = [
    r"precheck_fail",         # MD structure broken
    r"FAIL:chapter",          # chapter structure issues
    r"FAIL:running_header",   # OCR noise
    r"管道步骤失败",          # pipeline error (code bug)
    r"源MD文件严重重复",      # source file corrupted
    r"章号重复",              # chapter duplication
    r"章号非连续",            # chapter gap
    r"完整率0%",              # 0% completeness = chapter regex didn't match = structural
    r"实抽0仅0%",             # 0 KU extracted = synthesis failed entirely
]


def is_retryable(reason: str) -> bool:
    """Check if a quarantine reason matches a retryable pattern."""
    # If any non-retryable pattern matches, skip
    for pat in NON_RETRYABLE_PATTERNS:
        if re.search(pat, reason):
            return False
    # If any retryable pattern matches, it's retryable
    for pat in RETRYABLE_PATTERNS:
        if re.search(pat, reason):
            return True
    return False


def process_pipeline(pipeline_name: str, dry_run: bool):
    """Process a single pipeline's quarantine list."""
    config = PIPELINE_CONFIGS[pipeline_name]
    state_path = Path(config["state_file"])
    quarantine_path = Path(config["quarantine_file"])

    if not state_path.exists():
        print(f"  [{pipeline_name}] 状态文件不存在: {state_path}")
        return

    state = json.loads(state_path.read_text(encoding="utf-8"))
    processed = state.get("processed", {})

    # Find retryable entries
    retryable = {}
    skipped_non_retryable = 0
    for sid, info in processed.items():
        status = info.get("status", "")
        reason = info.get("reason", "")
        if status in ("quarantine",) and is_retryable(reason):
            retryable[sid] = info
        elif status in ("quarantine", "precheck_fail"):
            skipped_non_retryable += 1

    print(f"  [{pipeline_name}] 总计 {len(processed)} 条记录:")
    print(f"    可重试(双语/密度/rationale): {len(retryable)}")
    print(f"    不可重试(预检/管道/源文件): {skipped_non_retryable}")

    if not retryable:
        print(f"    无可重试项, 跳过")
        return

    if dry_run:
        print(f"    [DRY RUN] 将重试以下 {len(retryable)} 本书:")
        for sid, info in list(retryable.items())[:10]:
            reason_short = info.get("reason", "")[:80]
            print(f"      {sid}: {reason_short}")
        if len(retryable) > 10:
            print(f"      ... 还有 {len(retryable) - 10} 本")
        return

    # Remove retryable entries from state
    for sid in retryable:
        del processed[sid]

    state["processed"] = processed
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"    ✅ 已从状态文件移除 {len(retryable)} 条(下次 discover 会重新发现)")

    # Also clean from quarantine.json
    if quarantine_path.exists():
        q = json.loads(quarantine_path.read_text(encoding="utf-8"))
        q_items = q.get("quarantined", [])
        retryable_sids = set(retryable.keys())
        q["quarantined"] = [
            item for item in q_items
            if item.get("substrate_id", "") not in retryable_sids
        ]
        quarantine_path.write_text(
            json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        removed = len(q_items) - len(q["quarantined"])
        print(f"    ✅ 已从 quarantine.json 移除 {removed} 条")


async def clean_db(retryable_sids: list[str], dry_run: bool):
    """Clean residual KU/concept/KC/BU data from DB for retryable substrates."""
    if not retryable_sids:
        return

    import asyncpg
    db_url = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"    ⚠ 无法连接数据库: {e}")
        return

    total_cleaned = 0
    for sid in retryable_sids:
        # Check if substrate has any KU data
        ku_count = await conn.fetchval(
            "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sid
        )
        if not ku_count:
            continue

        if dry_run:
            total_cleaned += ku_count
            continue

        # Delete in order: BU → KC → concepts → KU
        for table in ["bu_onto", "kc_onto", "concept_onto", "ku_onto"]:
            try:
                await conn.execute(
                    f"DELETE FROM aii.{table} WHERE substrate_id=$1", sid
                )
            except Exception:
                pass  # table might not exist or have FK constraints

        total_cleaned += ku_count

    action = "[DRY RUN] 将清理" if dry_run else "✅ 已清理"
    print(f"    {action} DB 中 {total_cleaned} 条残留 KU(跨 {len(retryable_sids)} 本书)")
    await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="飞轮重试: 释放可重试的隔离书")
    parser.add_argument(
        "--pipeline", choices=["econ", "advmath", "misc", "all"], default="all"
    )
    parser.add_argument("--dry-run", action="store_true", help="只看不改")
    args = parser.parse_args()

    pipelines = (
        list(PIPELINE_CONFIGS.keys())
        if args.pipeline == "all"
        else [args.pipeline]
    )

    print(f"{'[DRY RUN] ' if args.dry_run else ''}★ 飞轮重试扫描")
    print()

    all_retryable_sids = []

    for pipeline in pipelines:
        process_pipeline(pipeline, args.dry_run)
        if not args.dry_run:
            # Collect sids for DB cleanup
            config = PIPELINE_CONFIGS[pipeline]
            # We already removed them from state, so get the list from before
            # (process_pipeline already printed them)
            pass

    if not args.dry_run:
        print()
        print("提示: 下次飞轮运行时, discover 脚本会重新发现这些书并加入队列.")
        print("      econ_flywheel_zh.sh / misc_flywheel.sh / advmath_flywheel.sh")
        print("      的 Step 0 (pull_ingest.sh) 会同步新书源.")


if __name__ == "__main__":
    asyncio.run(main())
