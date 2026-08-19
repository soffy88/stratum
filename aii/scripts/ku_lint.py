#!/usr/bin/env python3
"""B 仓(aii_refined)机械式健康检查 + 幂等打标 — 纯 SQL, 零 LLM。

对齐 pi-llm-wiki wiki_lint 模式, 针对 B 仓终点知识库(rf schema):
  A 仓 = 源 KU(每本书都保留); B 仓 = canonical 收敛终点。

三阶段闭环(全部确定性):
  1. 体检     : 13 项纯 SQL 检查
  2. 打标     : 结果 upsert 到 rf.ku_health_issues(类级: ku_id='*');
               本轮消失的 open 项自动置 fixed(fixed_by='lint_auto')
  3. 修复     : --fix-safe 只自动修零风险项(FK 断链删除),
               合并/删除类只生成候选清单 —— 守 B 仓「宁冗余不误删」

用法:
    .venv/bin/python scripts/ku_lint.py             # 体检+打标+报告
    .venv/bin/python scripts/ku_lint.py --json      # JSON(供 healer 消费)
    .venv/bin/python scripts/ku_lint.py --fix-safe  # 体检+打标+修零风险项
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

REFINED_URL = os.getenv(
    "REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined"
)
AII_URL = os.getenv(
    "AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg"
)

# (check_name, severity, 描述, 是否零风险可自动修)
CHECK_DEFS: list[tuple[str, str, str, bool]] = [
    ("orphan_ku", "crit", "无 refined_ku_concept 关联(B 仓命门: KU 必须挂概念)", False),
    ("broken_ku_concept", "crit", "ku_concept → 不存在的 refined_ku(FK 残留)", True),
    ("broken_edge_src", "crit", "directed_edge.src_concept → 不存在的概念", True),
    ("broken_edge_dst", "crit", "directed_edge.dst_concept → 不存在的概念", True),
    ("no_trace", "crit", "contributions 为空(无 A 仓来源追溯)", False),
    ("dup_hash", "warn", "point+natural_text 哈希重复(ku_dedup 未收敛)", False),
    ("weak_point", "warn", "point 过短(<5 字符)", False),
    ("no_embedding", "warn", "无 embedding 向量", False),
    ("grade_unverified", "warn", "grade 仍 unverified", False),
    ("ledger_failed", "warn", "decision_ledger 失败记录", False),
    ("lag_a2b", "info", "A→B 同步滞后", False),
    ("hyperedge_empty", "info", "refined_hyperedge 超边组件未启用", False),
    ("invariant_empty", "info", "refined_invariant 不变核组件未启用", False),
    ("edge_trust", "warn", "边可信度: explicit(EXTRACTED) 占比过低", False),
    ("isolated_concept", "info", "孤立概念(无任何边) 占比", False),
    ("no_span_rate", "warn", "Grounded 协议失败率(NO_SPAN 占比, 越高=抽取协议越弱)", False),
    ("not_entailed_rate", "info", "NLI 未支撑率(NOT_ENTAILED 占比, 打标不拒)", False),
]

CHECKS: list[dict] = []


def _run(conn, sql: str):
    return conn.fetchval(sql)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix-safe", action="store_true", help="自动修零风险项(FK 断链删除)")
    ap.add_argument("--min-level", default="info", choices=["info", "warn", "crit"])
    args = ap.parse_args()

    r = await asyncpg.connect(REFINED_URL)
    a = await asyncpg.connect(AII_URL)

    # ── 1. 体检(13 项确定性检查) ─────────────────────────────
    async def check(name: str, sql: str, conn=None) -> int:
        c = conn or r
        return await c.fetchval(sql) or 0

    counts = {
        "orphan_ku": await check("orphan_ku",
            "SELECT count(*) FROM rf.refined_ku k LEFT JOIN rf.refined_ku_concept kc"
            " ON kc.ku_id=k.ku_id WHERE kc.ku_id IS NULL"),
        "broken_ku_concept": await check("broken_ku_concept",
            "SELECT count(*) FROM rf.refined_ku_concept kc"
            " LEFT JOIN rf.refined_ku k ON k.ku_id=kc.ku_id WHERE k.ku_id IS NULL"),
        "broken_edge_src": await check("broken_edge_src",
            "SELECT count(*) FROM rf.refined_directed_edge e"
            " LEFT JOIN rf.refined_concept c ON c.concept_id=e.src_concept"
            " WHERE c.concept_id IS NULL"),
        "broken_edge_dst": await check("broken_edge_dst",
            "SELECT count(*) FROM rf.refined_directed_edge e"
            " LEFT JOIN rf.refined_concept c ON c.concept_id=e.dst_concept"
            " WHERE c.concept_id IS NULL"),
        "no_trace": await check("no_trace",
            "SELECT count(*) FROM rf.refined_ku WHERE contributions='[]'::jsonb"),
        "dup_hash": await check("dup_hash",
            "SELECT count(*) FROM (SELECT ku_id, row_number() OVER"
            " (PARTITION BY md5(lower(point||'|'||coalesce(natural_text,'')))) AS rn"
            " FROM rf.refined_ku) t WHERE t.rn>1"),
        "weak_point": await check("weak_point",
            "SELECT count(*) FROM rf.refined_ku WHERE point IS NULL OR length(point)<5"),
        "no_embedding": await check("no_embedding",
            "SELECT count(*) FROM rf.refined_ku WHERE embedding IS NULL"),
        "grade_unverified": await check("grade_unverified",
            "SELECT count(*) FROM rf.refined_ku WHERE grade='unverified'"),
        "ledger_failed": await check("ledger_failed",
            "SELECT count(*) FROM rf.decision_ledger WHERE"
            " verdict @> '{\"status\":\"failed\"}' OR verdict @> '{\"ok\":false}'"),
        "hyperedge_empty": 0 if await check("hyperedge_empty",
            "SELECT count(*) FROM rf.refined_hyperedge") else 1,
        "invariant_empty": 0 if await check("invariant_empty",
            "SELECT count(*) FROM rf.refined_invariant") else 1,
    }
    a_total = await a.fetchval("SELECT count(*) FROM aii.ku_onto")
    b_total = await r.fetchval("SELECT count(*) FROM rf.refined_ku")
    counts["lag_a2b"] = max(0, a_total - b_total)
    # Grounded/NLI 指标(近 7 天 trajectory 聚合)
    try:
        t_total = await a.fetchval(
            "SELECT count(*) FROM aii.trajectory_logs WHERE ts > now() - interval '7 days'")
        t_nospan = await a.fetchval(
            "SELECT count(*) FROM aii.trajectory_logs WHERE failure_mode IN"
            " ('NO_SPAN','NO_SOURCE') AND ts > now() - interval '7 days'")
        t_nli = await a.fetchval(
            "SELECT count(*) FROM aii.trajectory_logs WHERE failure_mode='NOT_ENTAILED'"
            " AND ts > now() - interval '7 days'")
        counts["no_span_rate"] = round(t_nospan / t_total * 100) if t_total else 0
        counts["not_entailed_rate"] = round(t_nli / t_total * 100) if t_total else 0
    except Exception:  # noqa: BLE001
        counts["no_span_rate"] = counts["not_entailed_rate"] = 0
    # 边可信度(graphify EXTRACTED/INFERRED 报告模式): explicit 占比
    exp_n = await check("edge_trust",
        "SELECT count(*) FROM rf.refined_directed_edge WHERE edge_source='explicit'")
    inf_n = await check("edge_trust",
        "SELECT count(*) FROM rf.refined_directed_edge WHERE edge_source='readout'")
    counts["edge_trust"] = 0 if (exp_n + inf_n) == 0 else round(inf_n / (exp_n + inf_n) * 100)
    # 孤立概念(无任何边)
    counts["isolated_concept"] = await check("isolated_concept",
        "SELECT count(*) FROM rf.refined_concept c WHERE NOT EXISTS ("
        " SELECT 1 FROM rf.refined_directed_edge e"
        " WHERE e.src_concept=c.concept_id OR e.dst_concept=c.concept_id)")

    # ── 2. 打标(幂等 upsert; 消失项自动 fixed) ────────────────
    await r.execute(
        "UPDATE rf.ku_health_issues SET status='stale' WHERE status='open'"
    )
    for name, sev, desc, _fixable in CHECK_DEFS:
        cnt = counts.get(name, 0)
        if cnt > 0:
            detail = json.dumps({"desc": desc, "count": cnt}, ensure_ascii=False)
            await r.execute(
                "INSERT INTO rf.ku_health_issues (ku_id, check_name, severity, detail)"
                " VALUES ('*', $1, $2, $3::jsonb)"
                " ON CONFLICT (ku_id, check_name) DO UPDATE"
                " SET last_seen=now(), detail=$3::jsonb, status='open'",
                name, sev, detail,
            )
        else:
            await r.execute(
                "UPDATE rf.ku_health_issues SET status='fixed', fixed_by='lint_auto',"
                " fixed_at=now() WHERE ku_id='*' AND check_name=$1 AND status='stale'",
                name,
            )
    # stale 且本轮未复现 → fixed(兜底, 覆盖异常路径)
    await r.execute(
        "UPDATE rf.ku_health_issues SET status='fixed', fixed_by='lint_auto',"
        " fixed_at=now() WHERE status='stale'"
    )

    # ── 3. 零风险修复(仅 --fix-safe) ──────────────────────────
    fixed_rows = 0
    if args.fix_safe:
        for name in ("broken_ku_concept", "broken_edge_src", "broken_edge_dst"):
            if counts.get(name, 0) == 0:
                continue
            if name == "broken_ku_concept":
                n = await r.execute(
                    "DELETE FROM rf.refined_ku_concept kc"
                    " USING rf.refined_ku k WHERE k.ku_id=kc.ku_id"
                    " AND k.ku_id IS NULL")
            else:
                col = "src_concept" if name == "broken_edge_src" else "dst_concept"
                n = await r.execute(
                    f"DELETE FROM rf.refined_directed_edge e"
                    f" USING rf.refined_concept c WHERE c.concept_id=e.{col}"
                    f" AND c.concept_id IS NULL")
            fixed_rows += getattr(n, "rowcount", 0) or 0
            await r.execute(
                "UPDATE rf.ku_health_issues SET status='fixed', fixed_by='healer_fix',"
                " fixed_at=now() WHERE ku_id='*' AND check_name=$1", name)

    # ── 4. 报告 ──────────────────────────────────────────────
    if args.json:
        print(json.dumps({
            "checks": [
                {"name": n, "severity": s, "desc": d, "count": counts.get(n, 0)}
                for n, s, d, _ in CHECK_DEFS
            ],
            "summary": {
                "crit": sum(1 for n, s, _, _ in CHECK_DEFS
                            if s == "crit" and counts.get(n, 0)),
                "warn": sum(1 for n, s, _, _ in CHECK_DEFS
                            if s == "warn" and counts.get(n, 0)),
                "fixed_rows": fixed_rows,
            },
        }, ensure_ascii=False, indent=1))
    else:
        order = {"crit": 0, "warn": 1, "info": 2}
        icons = {"crit": "🔴", "warn": "🟡", "info": "🔵"}
        for name, sev, desc, fixable in sorted(CHECK_DEFS,
                                               key=lambda x: order[x[1]]):
            cnt = counts.get(name, 0)
            if order[sev] > order[args.min_level]:
                continue
            fix = " [可自动修]" if fixable else ""
            print(f"{icons[sev]} {name}: {desc}{fix}  [{cnt}]")
        print(f"\n共 {len(CHECK_DEFS)} 项 | 打标完成 | "
              f"{'修复断链 ' + str(fixed_rows) + ' 行' if args.fix_safe else '未修复(--fix-safe 开启自动修)'}")

    await r.close()
    await a.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
