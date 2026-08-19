#!/usr/bin/env python3
"""★2026-08-10 论文精髓 → 可应用 Agent Skill 导出器 (book-to-skill + cangjie V3)。

数据源: aii_kg.bu_onto (paper BU 两层理解 + paper_v3_gate 排他性判官)。
每篇 worth_as_skill=true 的论文 → ~/.agents/skills/paper-<slug>/SKILL.md
(pi 及 3O agent 的 skills 加载目录 = 可直接被 agent 调用)。

SKILL.md 结构: problem_statement(解决什么) / use_when(何时用) /
method.steps(可执行步骤) / main_claims(结论) / v3.findings(排他性洞见) /
boundary_conditions(防误用) / dependencies(依赖)。

幂等: 已导出的记录在 watchdog/paper_skill_exported.json; 重跑跳过。
用法: .venv/bin/python scripts/paper_skill_export.py [--limit N] [--out DIR]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path.home() / ".agents" / "skills"
EXPORTED = ROOT / "watchdog" / "paper_skill_exported.json"
DSN = "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg"


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", (s or "").lower()).strip("-")
    return s[:50] or "paper"


def _li(items) -> str:
    if not items:
        return "- (无)"
    if isinstance(items, str):
        return items.strip()
    return "\n".join(f"- {x}" for x in items)


def _skill_md(row: dict) -> str:
    _sk_raw = row.get("agent_skill")
    sk = json.loads(_sk_raw) if isinstance(_sk_raw, str) else (_sk_raw or {})
    method = sk.get("method") or {}
    v3 = sk.get("v3") or {}
    _claims_raw = row.get("main_claims")
    claims = json.loads(_claims_raw) if isinstance(_claims_raw, str) else (_claims_raw or [])
    claims_txt = "\n".join(
        f"- {c.get('claim')}" for c in claims if c.get("claim")) if isinstance(claims, list) else str(claims)
    findings = v3.get("findings") or []
    findings_txt = "\n".join(
        f"- **{f.get('finding')}** (独有: {f.get('why')})" for f in findings if f.get("finding"))
    boundary = sk.get("boundary_conditions") or []
    deps = sk.get("dependencies") or []
    title = row.get("substrate_id")
    desc = (row.get("overview_oneline") or v3.get("novelty_note") or "")[:160]
    return f"""---
name: paper-{_slugify(row['substrate_id'])}
description: {desc}
---

# {title}

## 解决什么问题
{row.get('problem_statement') or '(无)'}

## 何时使用
{_li(sk.get('use_when'))}

## 方法 (可执行)
{method.get('approach') or '(无)'}

### 输入
{_li(method.get('inputs'))}

### 步骤
{_li(method.get('steps'))}

### 输出
{method.get('outputs') or '(无)'}

## 关键结论
{claims_txt or '(无)'}

## 论文独有洞见 (cangjie 排他性)
{findings_txt or '(无)'}

## 边界条件 (防误用)
{_li(boundary)}

## 依赖
{_li(deps)}
"""


def _load_exported() -> set[str]:
    try:
        return set(json.loads(EXPORTED.read_text()).get("ids", []))
    except Exception:
        return set()


def _save_exported(ids: set[str]) -> None:
    EXPORTED.parent.mkdir(parents=True, exist_ok=True)
    EXPORTED.write_text(json.dumps({"ids": sorted(ids)}, indent=2))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="本轮最多导出(0=全部未导出)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    import asyncpg
    conn = await asyncpg.connect(DSN, timeout=15)
    exported = _load_exported()
    try:
        rows = await conn.fetch(
            "SELECT substrate_id, problem_statement, overview_oneline, main_claims, agent_skill "
            "FROM aii.bu_onto "
            "WHERE doc_type='paper' AND agent_skill->'v3'->>'worth_as_skill'='true' "
            "AND agent_skill ? 'method' "
            "ORDER BY created_at DESC"
        )
    finally:
        await conn.close()

    out_dir = Path(args.out)
    new = 0
    for row in rows:
        sid = row["substrate_id"]
        if sid in exported:
            continue
        if args.limit and new >= args.limit:
            break
        slug = _slugify(sid)
        p = out_dir / f"paper-{slug}" / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_skill_md(dict(row)), encoding="utf-8")
        exported.add(sid)
        new += 1
        print(f"  📦 {p.name} ← {sid}")

    _save_exported(exported)
    print(f"\n完成: 新增 {new} 个论文技能 → {out_dir} (累计 {len(exported)}/{len(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
