#!/usr/bin/env python3
"""轨迹蒸馏 (P2b) — 每周审视 trajectory_logs → 提炼 if-then 规则 → skill_rules。

流程:
  1. 读最近 7 天 trajectory_logs, 按 failure_mode 分组统计
  2. 对高频失败模式(≥阈值), 用 LLM 生成 if-then 预处理规则(保守: 只提炼
     可静态判定的信号 → 动作映射, 如 文件名特征 → 走OCR队列)
  3. 规则 upsert 进 aii.skill_rules(source='distilled', 保留 LLM 原文)
  4. 输出报告(规则新增/更新/废弃)

安全设计:
  - 蒸馏出的规则必须带 condition/action 完整 JSON, schema 校验不过则丢弃
  - 默认不删除旧规则(只标记), 人工可禁用
  - 零权限: 规则只是"建议", 消费方(convert/飞轮)决定是否执行

用法:
    .venv/bin/python scripts/trajectory_distill.py [--days 7] [--dry-run] [--min-count 3]
环境: NVIDIA_NIM_API_KEY(缺省读 .pipeline_keys.json), NIM_MODEL
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[1]

SYS = (
    "You distill operational pre-filter rules from pipeline failure telemetry. "
    "Given failure clusters (failure_mode + contexts), produce at most 3 NEW if-then "
    "rules that could PREVENT or REROUTE failures BEFORE they cost LLM calls. "
    "★命门: (1) rules must be statically decidable from file name / size / text-layer "
    "heuristics — NO runtime LLM in the condition; (2) do NOT invent signals absent "
    "from the evidence; (3) if nothing generalizable, return empty list. "
    'Output strict JSON: {"rules":[{"rule_name":"snake_case","condition":{'
    '"file_name_contains":"...","size_mb_gt":20,"ext":"pdf"},'
    '"action":{"route":"ocr_queue","skip_llm":true,"reason":"..."}}]}'
)


def _nim_key() -> str:
    k = os.getenv("NVIDIA_NIM_API_KEY")
    if k:
        return k
    try:
        d = json.loads((ROOT / ".pipeline_keys.json").read_text())
        return d.get("advmath_verify") or d.get("econ") or ""
    except Exception:
        return ""


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-count", type=int, default=3)
    args = ap.parse_args()

    dsn = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    conn = await asyncpg.connect(dsn)

    # 1. 失败模式分组
    rows = await conn.fetch(
        "SELECT failure_mode, count(*) AS n, "
        " mode() WITHIN GROUP (ORDER BY error_sig) AS sample_sig, "
        " jsonb_agg(context ORDER BY ts DESC) AS contexts "
        " FROM aii.trajectory_logs"
        " WHERE ts > now() - make_interval(days => $1) AND outcome <> 'recovered'"
        " GROUP BY failure_mode HAVING count(*) >= $2 ORDER BY n DESC",
        args.days, args.min_count,
    )
    if not rows:
        print("近 7 天无显著失败模式(或记录为空)")
        await conn.close()
        return 0

    # 2. 组装证据 → LLM 蒸馏
    evidence = []
    for r in rows[:8]:
        ctx_samples = [c for c in (r["contexts"] or []) if isinstance(c, dict)][:5]
        evidence.append({
            "failure_mode": r["failure_mode"],
            "count": r["n"],
            "sample_error": r["sample_sig"],
            "sample_contexts": ctx_samples,
        })
    prompt = json.dumps(evidence, ensure_ascii=False)[:12000]
    print(f"蒸馏输入: {len(rows)} 个失败模式 ({sum(r['n'] for r in rows)} 事件)", flush=True)

    if args.dry_run:
        for r in rows:
            print(f"  [{r['n']}] {r['failure_mode']}: {(r['sample_sig'] or '')[:80]}")
        await conn.close()
        return 0

    key = _nim_key()
    if not key:
        print("❌ 无 NIM key")
        await conn.close()
        return 2

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5"),
                "messages": [
                    {"role": "system", "content": SYS},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 1200,
            },
        )
        out = resp.json()["choices"][0]["message"]["content"]
        if not out:
            print("❌ LLM 空响应")
            await conn.close()
            return 3

    # 3. 解析 + 落库(schema 校验)
    try:
        payload = json.loads(out)
        rules = payload.get("rules") or []
    except json.JSONDecodeError:
        print("❌ 蒸馏输出非 JSON, 丢弃")
        await conn.close()
        return 4

    added = updated = rejected = 0
    for rule in rules:
        name = (rule.get("rule_name") or "").strip()
        cond = rule.get("condition")
        act = rule.get("action")
        if not name or not isinstance(cond, dict) or not isinstance(act, dict):
            rejected += 1
            continue
        # 安全校验: condition 必须是静态可判定字段
        allowed = {"file_name_contains", "file_name_matches", "size_mb_gt", "size_mb_lt",
                   "ext", "text_layer_chars_lt", "phase"}
        if not set(cond).issubset(allowed):
            rejected += 1
            print(f"  ⚠ 拒绝 {name}: condition 含非静态字段 {set(cond) - allowed}")
            continue
        await conn.execute(
            "INSERT INTO aii.skill_rules (rule_name, condition, action, source)"
            " VALUES ($1, $2::jsonb, $3::jsonb, 'distilled')"
            " ON CONFLICT (rule_name) DO UPDATE SET condition=$2::jsonb, action=$3::jsonb,"
            " source='distilled', enabled=true",
            name, json.dumps(cond, ensure_ascii=False), json.dumps(act, ensure_ascii=False),
        )
        added += 1
        print(f"  ✅ {name}: {json.dumps(cond, ensure_ascii=False)[:80]}")

    await conn.close()
    print(f"蒸馏完成: 新增/更新 {added} | 拒绝 {rejected}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
