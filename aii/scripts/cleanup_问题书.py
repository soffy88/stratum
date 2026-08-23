#!/usr/bin/env python3
"""★问题书清理: 扫描 83 本未修复的问题书, 分类处理.

用法:
  python3 scripts/cleanup_问题书.py              # 执行清理
  python3 scripts/cleanup_问题书.py --dry-run    # 只看不动
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # aii/scripts/.. → aii/
sys.path.insert(0, str(ROOT))

STATE_FILE = ROOT / "econ_pipeline" / "flywheel_zh_state.json"
QUARANTINE_FILE = ROOT / "econ_pipeline" / "quarantine.json"
ISSUE_DIR = ROOT.parent / "aii" / "问题书"  # 上层: stratum/aii/问题书


def main():
    ap = argparse.ArgumentParser(description="问题书清理")
    ap.add_argument("--dry-run", action="store_true", help="只看不动")
    args = ap.parse_args()

    if not STATE_FILE.exists():
        print(f"❌ 状态文件不存在: {STATE_FILE}")
        sys.exit(1)

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    processed = state.get("processed", {})

    # 读问题书
    from collections import defaultdict
    issue_books = []  # list of (sid, cat, detail, md_path)
    for cat in ["管道失败", "预检失败", "质量门未通过"]:
        cat_dir = ISSUE_DIR / "未修复" / cat
        if not cat_dir.exists():
            continue
        for f in sorted(cat_dir.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            issue_books.append({
                "sid": d["substrate_id"],
                "cat": cat,
                "detail": d.get("reason_detail", ""),
                "md_path": d.get("md_path", ""),
                "md_exists": os.path.exists(d.get("md_path", "")),
            })

    print(f"📋 问题书总计: {len(issue_books)} 本")
    print()

    # 分类处理
    skip_sids = []      # MD 缺失, 标记为 skip
    retry_sids = []     # MD 存在 but 管道失败 or 质量门(可重试)
    precheck_retry = [] # 预检失败但 MD 存在 (chapter_dup)

    for b in issue_books:
        if not b["md_exists"]:
            skip_sids.append(b)
        elif b["cat"] == "预检失败":
            precheck_retry.append(b)
        elif b["cat"] == "管道失败":
            retry_sids.append(b)  # MD 存在 + 管道失败 → 重试
        elif b["cat"] == "质量门未通过":
            retry_sids.append(b)  # MD 存在 + 质量门 → 重试

    print(f"🔴 标记为 skip (MD 已删除, 不可恢复): {len(skip_sids)} 本")
    if skip_sids and not args.dry_run:
        for b in skip_sids:
            sid = b["sid"]
            if sid in processed and processed[sid].get("status") in ("quarantine", "precheck_fail"):
                processed[sid] = {
                    "status": "skip",
                    "reason": f"MD文件已删除, 无法修复 (原: {b['cat']})",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }

    print(f"🟢 可重试 (MD 存在, 可重新处理): {len(retry_sids) + len(precheck_retry)} 本")
    if retry_sids and not args.dry_run:
        for b in retry_sids:
            sid = b["sid"]
            if sid in processed:
                # 从 state 中删除, 下次 discover 会重新发现重跑
                del processed[sid]

    if precheck_retry and not args.dry_run:
        # chapter_dup 的书: 修了预检后, 从 state 删除让其重新发现
        for b in precheck_retry:
            sid = b["sid"]
            if sid in processed:
                del processed[sid]

    # 一并清除 quarantine.json 中对应的条目
    q = {}
    if QUARANTINE_FILE.exists():
        q = json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
    q_items = q.get("quarantined", [])

    all_affected_sids = set()
    for b in skip_sids + retry_sids + precheck_retry:
        all_affected_sids.add(b["sid"])

    if all_affected_sids and not args.dry_run:
        old_len = len(q_items)
        q["quarantined"] = [item for item in q_items if item.get("substrate_id", "") not in all_affected_sids]
        removed = old_len - len(q["quarantined"])
        print(f"🧹 从 quarantine.json 清除 {removed} 条")

    # 报告
    print()
    print("=" * 60)
    print("📊 处理报告")
    print("=" * 60)

    for label, lst in [("🔴 Skip (MD 缺失)", skip_sids), ("🟢 Retry (MD 存在)", retry_sids), ("🟢 Precheck retry", precheck_retry)]:
        if lst:
            print(f"\n{label} ({len(lst)}):")
            for b in lst:
                detail_short = b["detail"][:60]
                print(f"  {b['sid']}: {b['cat']} | {detail_short}")

    if args.dry_run:
        print()
        print("⚠️ DRY RUN — 未写入任何修改")
        return

    # 写回
    state["processed"] = processed
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ flywheel_zh_state.json 已更新 ({len(processed)} 条记录)")

    if q:
        QUARANTINE_FILE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ quarantine.json 已更新")

    print()
    print("📋 后续操作:")
    print("  1. 运行飞轮重试: python3 scripts/flywheel_retry_quarantined.py --pipeline econ")
    print("  2. 运行飞轮: bash scripts/econ_flywheel_zh.sh")
    print("  3. 验证: 问题书中的书应已减少")


if __name__ == "__main__":
    main()