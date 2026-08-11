#!/usr/bin/env python3
"""轨迹 reflect (graphify 启发④) — 确定性失败信号聚合, 零 LLM。

graphify reflect 的确定性版: 按 failure_mode 聚合 trajectory_logs 的
失败/恢复信号 → 标记 useful / dead_end → 写入 skill_rules(仅标记, 不自动执行)。

规则:
  useful    = 该失败模式有 recovered 记录(管道能自愈) → 维持现状
  dead_end  = 失败 ≥ N 次 且 recovered = 0(连续白折腾) → 生成规则
              {action: {skip: true, dead_end: true, reason: 统计摘要}}
              → 消费方(飞轮预筛)可据此跳过无效重试, 省 NIM/时间

用法:
    .venv/bin/python scripts/trajectory_reflect.py [--days 7] [--min-fail 5] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

DSN = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-fail", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(DSN)
    rows = await conn.fetch(
        "SELECT failure_mode,"
        " count(*) FILTER (WHERE outcome='failed')   AS n_fail,"
        " count(*) FILTER (WHERE outcome='recovered') AS n_rec,"
        " count(*) FILTER (WHERE outcome='degraded')  AS n_deg"
        " FROM aii.trajectory_logs"
        " WHERE ts > now() - make_interval(days => $1)"
        " GROUP BY failure_mode ORDER BY n_fail DESC",
        args.days,
    )
    if not rows:
        print("近 7 天无轨迹记录(埋点刚上线, 飞轮跑起来后自然积累)")
        await conn.close()
        return 0

    print(f"{'failure_mode':<28} {'失败':>5} {'恢复':>5} {'降级':>5}  判定")
    marked = 0
    for r in rows:
        verdict = "useful" if r["n_rec"] > 0 else ("dead_end" if r["n_fail"] >= args.min_fail else "watch")
        print(f"{r['failure_mode']:<28} {r['n_fail']:>5} {r['n_rec']:>5} {r['n_deg']:>5}  {verdict}")
        if verdict != "dead_end":
            continue
        rule_name = f"dead_end_{r['failure_mode'][:40]}"
        action = {
            "skip": True,
            "dead_end": True,
            "reason": f"reflect: {r['n_fail']} 次失败 0 次恢复(近 {args.days} 天)",
        }
        exists = await conn.fetchval(
            "SELECT rule_id FROM aii.skill_rules WHERE rule_name=$1", rule_name)
        if exists and not args.dry_run:
            await conn.execute(
                "UPDATE aii.skill_rules SET action=$2::jsonb, enabled=true WHERE rule_name=$1",
                rule_name, json.dumps(action, ensure_ascii=False))
        elif not exists and not args.dry_run:
            await conn.execute(
                "INSERT INTO aii.skill_rules (rule_name, condition, action, source)"
                " VALUES ($1, $2::jsonb, $3::jsonb, 'reflect')",
                rule_name,
                json.dumps({"failure_mode": r["failure_mode"]}),
                json.dumps(action, ensure_ascii=False))
        marked += 1
        if not args.dry_run:
            print(f"  → 已写 skill_rules: {rule_name}")

    await conn.close()
    print(f"\nreflect 完成: dead_end 标记 {marked} ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
