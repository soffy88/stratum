#!/usr/bin/env python3
"""B 仓 → Agent Skill 导出器 (book-to-skill 启发 P0) — 确定性, 零 LLM。

把 B 仓(aii_refined)主题知识导出为标准 Agent Skills 包:
  ~/.agents/skills/<theme-slug>/
    SKILL.md        主题心智模型(summary + 核心概念 + 关键关系 + 加载指引)
    glossary.md     主题内概念表(name/name_zh/ku_count)
    patterns.md     主题内 derives/explains 关系模式
    cheatsheet.md   核心概念 → 定义 → 代表 KU(point) 决策表
    ku_index.md     主题 KU 索引(point/type, 按 ku_count 排序)

复用全部既有资产(主题/概念/边/KU), 纯 SQL 聚合 + 模板拼装, 无 LLM 调用。
Agent Skills 开放标准(~/.agents/skills, Copilot CLI/Amp/Claude Code/pi 通用)。

用法:
    .venv/bin/python scripts/skill_export.py [--out ~/.agents/skills] [--min-ku 3] [--dry-run]
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

REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
DEFAULT_OUT = Path.home() / ".agents" / "skills"


def slugify(name: str) -> str:
    """slug 保留 CJK(中文主题名可读), 其余转连字符。"""
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", (name or "").lower()).strip("-")
    return s[:60] or "theme"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--min-ku", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(REFINED_URL)

    # 1. 全量主题
    themes = await conn.fetch(
        "SELECT kc_id, theme_name, theme_name_en, summary, summary_zh"
        " FROM rf.refined_theme_kc WHERE is_current ORDER BY kc_id")
    # 2. 主题 → KU(经 kc_member)
    members = await conn.fetch(
        "SELECT kc_id, ku_id FROM rf.refined_kc_member")
    ku_of_theme: dict[int, list[str]] = {}
    for m in members:
        ku_of_theme.setdefault(m["kc_id"], []).append(m["ku_id"])
    # 3. KU → 概念 / KU 详情
    ku_concepts = await conn.fetch(
        "SELECT ku_id, concept_id FROM rf.refined_ku_concept")
    ku_concept_map: dict[str, int] = {r["ku_id"]: r["concept_id"] for r in ku_concepts}
    kus = await conn.fetch(
        "SELECT ku_id, point, point_zh, ku_type FROM rf.refined_ku")
    ku_info = {r["ku_id"]: r for r in kus}
    concepts = await conn.fetch(
        "SELECT concept_id, name, name_zh, aliases FROM rf.refined_concept")
    concept_info = {r["concept_id"]: r for r in concepts}
    edges = await conn.fetch(
        "SELECT src_concept, dst_concept, relation_type FROM rf.refined_directed_edge")
    # 概念 ku_count
    ku_count_by_concept: dict[int, int] = {}
    for ku_id, cid in ku_concept_map.items():
        ku_count_by_concept[cid] = ku_count_by_concept.get(cid, 0) + 1

    out_root = Path(args.out)
    written = 0
    for th in themes:
        kus_of = ku_of_theme.get(th["kc_id"], [])
        if len(kus_of) < args.min_ku:
            continue
        slug = slugify(th["theme_name_en"] or th["theme_name"] or f"theme-{th['kc_id']}")
        # 主题内概念(按 ku_count 降序)
        cid_counts: dict[int, int] = {}
        for ku_id in kus_of:
            cid = ku_concept_map.get(ku_id)
            if cid:
                cid_counts[cid] = cid_counts.get(cid, 0) + 1
        theme_concepts = sorted(cid_counts.items(), key=lambda x: -x[1])
        # 主题内边(两端概念都在主题内)
        cid_set = set(cid_counts)
        theme_edges = [e for e in edges
                       if e["src_concept"] in cid_set and e["dst_concept"] in cid_set]

        files = _render_pack(th, kus_of, ku_info, theme_concepts, concept_info,
                             theme_edges, ku_concept_map)
        if args.dry_run:
            total = sum(len(v) for v in files.values())
            print(f"[dry] {slug}: {len(kus_of)} KU | {len(theme_concepts)} 概念"
                  f" | {len(theme_edges)} 边 | {total//1024}KB")
            written += 1
            continue
        pkg = out_root / slug
        pkg.mkdir(parents=True, exist_ok=True)
        for fname, content in files.items():
            (pkg / fname).write_text(content, encoding="utf-8")
        written += 1

    await conn.close()
    print(f"完成: {written} 个技能包 → {out_root} ({'DRY-RUN' if args.dry_run else '已写入'})")
    return 0


def _render_pack(th, kus_of, ku_info, theme_concepts, concept_info,
                 theme_edges, ku_concept_map) -> dict[str, str]:
    slug = slugify(th["theme_name_en"] or th["theme_name"] or "")
    en = th["theme_name_en"] or th["theme_name"] or slug
    zh = th["theme_name"] or ""
    summary = th["summary"] or ""
    summary_zh = th["summary_zh"] or ""

    # 核心概念(top 10 by ku_count)
    top_concepts = theme_concepts[:10]
    core_lines = []
    for cid, cnt in top_concepts:
        c = concept_info.get(cid, {})
        core_lines.append(f"- **{c.get('name') or cid}**"
                          f"{f"（{c.get('name_zh')}）" if c.get("name_zh") else ""}"
                          f" — {cnt} KU 挂载")
    # 关键边
    rel_lines = []
    for e in theme_edges[:12]:
        s = concept_info.get(e["src_concept"], {}).get("name", "?")
        d = concept_info.get(e["dst_concept"], {}).get("name", "?")
        rel_lines.append(f"- {s} --{e['relation_type']}--> {d}")
    # cheatsheet 代表 KU
    sheet_lines = []
    for cid, cnt in top_concepts[:8]:
        c = concept_info.get(cid, {})
        # 找该概念下主题内一条 KU
        rep_ku = next((k for k in kus_of if ku_concept_map.get(k) == cid), None)
        rep = ku_info.get(rep_ku, {}) if rep_ku else {}
        point = (rep.get("point") or rep.get("point_zh") or "")[:100]
        sheet_lines.append(
            f"| {c.get('name') or cid} | {point} | {rep.get('ku_type') or '-'} |")
    # glossary
    gloss_lines = []
    for cid, cnt in theme_concepts:
        c = concept_info.get(cid, {})
        gloss_lines.append(
            f"- **{c.get('name') or cid}**"
            f"{f"（{c.get('name_zh')}）" if c.get("name_zh") else ""}"
            f" — {cnt} KU")
    # ku_index
    ku_lines = []
    for ku_id in kus_of[:100]:
        k = ku_info.get(ku_id, {})
        pt = (k.get("point") or k.get("point_zh") or "")[:90]
        ku_lines.append(f"- [{k.get('ku_type') or '?'}] {pt}")
    if len(kus_of) > 100:
        ku_lines.append(f"\n<!-- 共 {len(kus_of)} KU, 展示前 100 -->")

    skill = f"""---
name: {slug}
description: "{zh or en} — {summary_zh or summary}"[:120]
---

# {en}{f"（{zh}）" if zh else ""}

{summary_zh or summary}

## 核心心智模型（Core Concepts）

{chr(10).join(core_lines) if core_lines else "- (主题内概念待补)"}

## 关键关系（Relations）

{chr(10).join(rel_lines) if rel_lines else "- (主题内边待补)"}

## 使用方式

查询本主题知识时按需加载:
- `glossary.md` — 概念术语表
- `patterns.md` — 推导/解释关系模式
- `cheatsheet.md` — 概念→定义速查表
- `ku_index.md` — 知识单元索引
"""
    patterns = f"""# 关系模式 — {en}

## derives（推导链）

{chr(10).join(rel_lines) if rel_lines else "- 暂无"}

## 说明

关系来自 B 仓 readout(explicit/inferred 标注见库)。
"""
    cheatsheet = f"""# 速查表 — {en}

| 概念 | 代表知识 | 类型 |
|---|---|---|
{chr(10).join(sheet_lines) if sheet_lines else "|-|-|-|"}
"""
    glossary = f"""# 术语表 — {en}

{chr(10).join(gloss_lines) if gloss_lines else "- 暂无"}
"""
    ku_index = f"""# KU 索引 — {en}（{len(kus_of)} 条）

{chr(10).join(ku_lines)}
"""
    return {"SKILL.md": skill, "glossary.md": glossary,
            "patterns.md": patterns, "cheatsheet.md": cheatsheet,
            "ku_index.md": ku_index}


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
