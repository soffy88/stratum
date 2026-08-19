#!/usr/bin/env python3
"""B 仓知识 → Obsidian Vault 导出器 — 直接用本项目知识学习/记笔记。

Obsidian 核心能力全部命中:
  - markdown 原生(.md + frontmatter tags) → 搜索/标签筛选
  - [[双链]] 概念↔主题↔KU → Graph View 自动显示知识网络
  - 本地优先 → 打开即用, 个人笔记区与检索打通

结构:
  vault/
  ├── 00-使用说明.md            # 打开方式 + 学习路径建议
  ├── 01-索引/00-KU总索引.md     # 主题 → 概念 → KU 三层索引(双链)
  ├── 02-主题/<theme>.md        # 主题心智模型 + 核心概念双链 + 关系
  ├── 03-概念/<concept>.md      # 定义/别名/挂载KU双链/相关概念双链
  ├── 04-KU/<ku>.md             # 命题/证据quote/类型/来源/概念双链
  └── 05-个人笔记/              # 你的笔记区(= ~/.stratum/notes, 检索已打通)

默认精选模式(--full 全量): 主题全量 + 每主题核心概念(top 8) + 每概念代表 KU(top 3)。
用法:
    .venv/bin/python scripts/obsidian_vault.py [--out ~/.stratum/vault] [--full] [--dry-run]
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
AII_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")


def _safe(name: str, maxlen: int = 60) -> str:
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "-", (name or "untitled")).strip()
    return s[:maxlen] or "untitled"


def _link(name: str) -> str:
    """Obsidian 双链(路径内文件名唯一化由 _safe 保证)。"""
    return f"[[{_safe(name)}]]"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/.stratum/vault"))
    ap.add_argument("--full", action="store_true", help="全量模式(不推荐, 页数巨大)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(REFINED_URL)

    # ── 0. 康奈尔笔记(A 仓 stratum 表) ─────────────────────
    cornell_rows = []
    try:
        aconn = await asyncpg.connect(AII_URL)
        cornell_rows = await aconn.fetch(
            "SELECT topic_id, title, subject, content FROM stratum.cornell_notes"
            " WHERE source='machine' AND deleted_at IS NULL ORDER BY created_at DESC")
        await aconn.close()
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ 康奈尔读取失败: {e}", flush=True)

    # ── 1. 全量数据聚合 ─────────────────────────────────────
    themes = await conn.fetch(
        "SELECT kc_id, theme_name, theme_name_en, summary, summary_zh"
        " FROM rf.refined_theme_kc WHERE is_current ORDER BY kc_id")
    members = await conn.fetch("SELECT kc_id, ku_id FROM rf.refined_kc_member")
    ku_of_theme: dict[int, list[str]] = {}
    for m in members:
        ku_of_theme.setdefault(m["kc_id"], []).append(m["ku_id"])
    ku_concepts = await conn.fetch("SELECT ku_id, concept_id FROM rf.refined_ku_concept")
    ku_concept_map: dict[str, int] = {r["ku_id"]: r["concept_id"] for r in ku_concepts}
    kus = await conn.fetch(
        "SELECT ku_id, point, point_zh, ku_type, natural_text, natural_text_zh,"
        " contributions FROM rf.refined_ku")
    ku_info = {r["ku_id"]: r for r in kus}
    concepts = await conn.fetch(
        "SELECT concept_id, name, name_zh, aliases FROM rf.refined_concept")
    concept_info = {r["concept_id"]: r for r in concepts}
    edges = await conn.fetch(
        "SELECT src_concept, dst_concept, relation_type FROM rf.refined_directed_edge")
    ku_count_by_concept: dict[int, int] = {}
    for ku_id, cid in ku_concept_map.items():
        ku_count_by_concept[cid] = ku_count_by_concept.get(cid, 0) + 1

    # ── 2. 精选范围(默认: 主题全 + 每主题 top8 概念 + 每概念 top3 KU) ──
    selected_concepts: set[int] = set()
    selected_kus: set[str] = set()
    theme_meta: dict[int, dict] = {}
    for th in themes:
        kus_of = ku_of_theme.get(th["kc_id"], [])
        cid_counts: dict[int, int] = {}
        for ku_id in kus_of:
            cid = ku_concept_map.get(ku_id)
            if cid:
                cid_counts[cid] = cid_counts.get(cid, 0) + 1
        top_c = sorted(cid_counts.items(), key=lambda x: -x[1])
        keep_c = top_c if args.full else top_c[:8]
        for cid, _ in keep_c:
            selected_concepts.add(cid)
        # 每概念代表 KU(top3 by 主题内挂载顺序)
        for cid, _ in keep_c:
            kus_c = [k for k in kus_of if ku_concept_map.get(k) == cid]
            for k in (kus_c if args.full else kus_c[:3]):
                selected_kus.add(k)
        theme_meta[th["kc_id"]] = {
            "theme": th, "kus": kus_of, "concepts": keep_c,
        }

    print(f"精选: {len(themes)} 主题 | {len(selected_concepts)} 概念 | {len(selected_kus)} KU",
          flush=True)

    if args.dry_run:
        await conn.close()
        print("(DRY-RUN)")
        return 0

    # ── 3. 写 vault ─────────────────────────────────────────
    root = Path(args.out)
    (root / "01-索引").mkdir(parents=True, exist_ok=True)
    (root / "02-主题").mkdir(parents=True, exist_ok=True)
    (root / "03-概念").mkdir(parents=True, exist_ok=True)
    (root / "04-KU").mkdir(parents=True, exist_ok=True)
    (root / "06-康奈尔").mkdir(parents=True, exist_ok=True)
    # 个人笔记区 = 检索 personal 层(软链统一, Obsidian 跟随软链)
    notes_dir = Path.home() / ".stratum" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    pdir = root / "05-个人笔记"
    if pdir.is_symlink():
        pass
    elif pdir.exists():
        import shutil
        shutil.rmtree(pdir)
        pdir.symlink_to(notes_dir, target_is_directory=True)
    else:
        pdir.symlink_to(notes_dir, target_is_directory=True)
    (notes_dir / "README.md").write_text(
        "此目录是 Obsidian Vault 的『个人笔记区』(= ~/.stratum/notes, 检索 personal 层)。\n"
        "在这里记笔记/双链概念, 项目检索自动包含。\n", encoding="utf-8")

    n_theme = n_concept = n_ku = 0

    # 概念页(先写, 供双链目标)
    concept_pages: dict[int, str] = {}
    for cid in selected_concepts:
        c = concept_info.get(cid, {})
        name = _safe(c.get("name") or f"concept-{cid}")
        concept_pages[cid] = name
        n_concept += 1

    # KU 页
    ku_pages: dict[str, str] = {}
    for ku_id in selected_kus:
        k = ku_info.get(ku_id, {})
        pt = (k.get("point") or k.get("point_zh") or "KU")[:50]
        ku_pages[ku_id] = _safe(pt)
        n_ku += 1

    # ── 概念页内容 ──────────────────────────────────────────
    for cid, name in concept_pages.items():
        c = concept_info.get(cid, {})
        cname = c.get("name") or name
        czh = c.get("name_zh") or ""
        aliases = c.get("aliases") or []
        # 挂载 KU(精选内)
        kus_c = [k for k in selected_kus if ku_concept_map.get(k) == cid]
        # 相关概念(边)
        rels = [e for e in edges
                if e["src_concept"] == cid or e["dst_concept"] == cid]
        lines = [
            "---",
            "tags: [概念]",
            f"ku_count: {ku_count_by_concept.get(cid, 0)}",
            "---",
            "",
            f"# {cname}{f'（{czh}）' if czh else ''}",
            "",
            f"挂载知识单元: {ku_count_by_concept.get(cid, 0)} 条",
            "",
        ]
        if aliases:
            al = aliases if isinstance(aliases, list) else [aliases]
            lines += ["**别名**: " + "、".join(str(a) for a in al[:8]), ""]
        if rels:
            lines += ["## 相关概念(知识网络)", ""]
            for e in rels[:10]:
                other = e["dst_concept"] if e["src_concept"] == cid else e["src_concept"]
                if other in concept_pages:
                    rel = "←" if e["dst_concept"] == cid else "→"
                    lines.append(f"- {_link(concept_info.get(other, {}).get('name') or str(other))} {rel} {e['relation_type']}")
            lines.append("")
        if kus_c:
            lines += ["## 挂载知识单元", ""]
            for k in kus_c[:10]:
                kp = ku_pages.get(k, k)
                lines.append(f"- {_link(kp)}")
            lines.append("")
        (root / "03-概念" / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")

    # ── 主题页 ──────────────────────────────────────────────
    theme_pages: dict[int, str] = {}
    for kc_id, meta in theme_meta.items():
        th = meta["theme"]
        ten = th["theme_name_en"] or "theme"
        tzh = th["theme_name"] or ""
        tname = _safe(f"{ten}")
        theme_pages[kc_id] = tname
        lines = [
            "---",
            "tags: [主题]",
            "---",
            "",
            f"# {ten}{f'（{tzh}）' if tzh else ''}",
            "",
            th["summary_zh"] or th["summary"] or "",
            "",
            "## 核心概念",
            "",
        ]
        for cid, cnt in meta["concepts"]:
            if cid in concept_pages:
                lines.append(f"- {_link(concept_pages[cid])}（{cnt} KU）")
        # 主题内边
        cid_set = {c for c, _ in meta["concepts"]}
        tedges = [e for e in edges
                  if e["src_concept"] in cid_set and e["dst_concept"] in cid_set]
        if tedges:
            lines += ["", "## 概念关系", ""]
            for e in tedges[:12]:
                s = concept_pages.get(e["src_concept"])
                d = concept_pages.get(e["dst_concept"])
                if s and d:
                    lines.append(f"- {_link(s)} --{e['relation_type']}--> {_link(d)}")
        lines += ["", "---", f"主题 KU 总数: {len(meta['kus'])}", ""]
        (root / "02-主题" / f"{tname}.md").write_text("\n".join(lines), encoding="utf-8")
        n_theme += 1

    # ── KU 页 ───────────────────────────────────────────────
    for ku_id, kp in ku_pages.items():
        k = ku_info.get(ku_id, {})
        pt = (k.get("point") or k.get("point_zh") or "KU")
        cid = ku_concept_map.get(ku_id)
        lines = [
            "---",
            f"tags: [KU, {k.get('ku_type') or 'conceptual'}]",
            "---",
            "",
            f"# {pt}",
            "",
        ]
        if cid and cid in concept_pages:
            lines += [f"概念: {_link(concept_pages[cid])}", ""]
        nt = (k.get("natural_text") or "")[:2000]
        if nt:
            lines += ["## 内容", "", nt, ""]
        ntz = (k.get("natural_text_zh") or "")
        if ntz and ntz != nt:
            lines += ["## 中文", "", ntz[:1500], ""]
        contrib = k.get("contributions")
        if contrib:
            try:
                cl = json.loads(contrib) if isinstance(contrib, str) else contrib
                if cl:
                    lines += ["## 来源(KU 溯源)", ""]
                    for c in cl[:3]:
                        lines += [
                            f"- `{c.get('source_book_id') or '?'}` · {c.get('facet') or 'main'}"
                            f" · raw: {c.get('raw_ku_id') or '?'}"]
                        frag = c.get("fragment_text") or ""
                        if frag:
                            lines += [f"  > {frag[:200]}", ""]
                    lines.append("")
            except Exception:  # noqa: BLE001
                pass
        (root / "04-KU" / f"{kp}.md").write_text("\n".join(lines), encoding="utf-8")

    # ── 康奈尔页(概念级学习卡) ─────────────────────────────
    cornell_pages: list[str] = []
    for cr in cornell_rows:
        cname = _safe(cr["title"] or "cornell")
        try:
            cj = json.loads(cr["content"]) if isinstance(cr["content"], str) else cr["content"]
        except Exception:  # noqa: BLE001
            cj = {}
        # topic_id "c{concept_id}-{slug}" → 概念双链
        clink = ""
        m = re.match(r"c(\d+)-", cr["topic_id"] or "")
        if m:
            cid = int(m.group(1))
            if cid in concept_pages:
                clink = f"概念: {_link(concept_pages[cid])}"
        lines = [
            "---",
            "tags: [康奈尔]",
            f"subject: {cr['subject'] or ''}",
            "---",
            "",
            f"# {cr['title']}",
            "",
        ]
        if clink:
            lines += [clink, ""]
        one = (cj.get("oneLiner") or "").strip()
        if one:
            lines += [f"> {one}", ""]
        cues = cj.get("cues") or []
        if cues:
            lines += ["## 线索栏(Cues)", ""]
            for c in cues:
                t = c.get("text") or c.get("hint") or ""
                if t:
                    lines.append(f"- {t}")
            lines.append("")
        mods = cj.get("modules") or []
        if not mods:
            mods = [{"title": "笔记", "body": (cj.get("notes") or "")}]
        lines += ["## 笔记(Notes)", ""]
        for mo in mods:
            t = mo.get("title") or ""
            b = (mo.get("body") or "").strip()
            if t:
                lines.append(f"### {t}")
            if b:
                lines.append(b)
            lines.append("")
        summ = (cj.get("summary") or "").strip()
        if summ:
            lines += ["## 总结(Summary)", "", summ, ""]
        drills = cj.get("drills") or []
        if drills:
            lines += ["## 练习(Drills)", ""]
            for d in drills[:6]:
                q = d.get("question") or d.get("q") or ""
                a = d.get("answer") or d.get("a") or ""
                if q:
                    lines.append(f"- **{q}**")
                    if a:
                        lines.append(f"  > {a}")
            lines.append("")
        (root / "06-康奈尔" / f"{cname}.md").write_text("\n".join(lines), encoding="utf-8")
        cornell_pages.append(cname)

    # 概念页反链康奈尔(在"挂载知识单元"后追加)
    if cornell_pages:
        for cid, name in concept_pages.items():
            cf = root / "03-概念" / f"{name}.md"
            if not cf.exists():
                continue
            txt = cf.read_text(encoding="utf-8")
            if "## 康奈尔笔记" in txt:
                continue
            linked = [f"- {_link(cp)}" for cr, cp in zip(cornell_rows, cornell_pages)
                      if re.match(rf"c{cid}\d*-", cr["topic_id"] or "")]
            if linked:
                txt += "\n## 康奈尔笔记\n\n" + "\n".join(linked) + "\n"
                cf.write_text(txt, encoding="utf-8")

    # ── 索引页 ──────────────────────────────────────────────
    idx_lines = [
        "---",
        "tags: [索引]",
        "---",
        "",
        "# 知识库总索引",
        "",
        "## 主题(学习路径起点)",
        "",
    ]
    for kc_id, meta in theme_meta.items():
        th = meta["theme"]
        idx_lines.append(
            f"- {_link(theme_pages.get(kc_id, th['theme_name_en'] or 'theme'))}"
            f" — {len(meta['kus'])} KU")
    if cornell_pages:
        idx_lines += ["", "## 康奈尔笔记(概念学习卡)", ""]
        for cp in cornell_pages[:40]:
            idx_lines.append(f"- {_link(cp)}")
        if len(cornell_pages) > 40:
            idx_lines.append(f"- …共 {len(cornell_pages)} 张")
    idx_lines += ["", "## 使用说明", "",
                  "1. **Obsidian 打开本目录**作为 Vault(设置里打开即可)",
                  "2. 从『02-主题』开始按兴趣学习 → 概念页 → KU 页(带原文证据)",
                  "3. 记笔记放『05-个人笔记』(自动进入项目检索 personal 层)",
                  "4. 图谱视图(Graph View)查看知识网络(双链自动生成)", ""]
    (root / "01-索引" / "00-KU总索引.md").write_text("\n".join(idx_lines), encoding="utf-8")

    # 使用说明
    (root / "00-使用说明.md").write_text(
        "# 使用说明\n\n"
        "本 Vault 由 stratum/aii 知识库自动生成(每日更新)。\n\n"
        "## 打开方式\n"
        "Obsidian → Open folder as vault → 选择本目录。\n\n"
        "## 学习路径\n"
        "1. `01-索引/00-KU总索引` → 选主题\n"
        "2. 主题页 → 核心概念(双链) → 概念页 → 挂载 KU(双链)\n"
        "3. KU 页含原文证据引用与来源\n\n"
        "## 康奈尔笔记\n"
        "`06-康奈尔/` 是概念级学习卡(线索/笔记/总结/练习), 由知识库自动生成。\n\n"
        "## 记笔记\n"
        "`05-个人笔记/` 是你的笔记区(=`~/.stratum/notes`), "
        "在此记笔记后, 项目的检索(personal 层)会自动包含。\n"
        "可在笔记中 `[[双链]]` 到任意概念/KU。\n\n"
        "## 更新\n"
        "每日自动重新导出(主题/概念/KU 页刷新, 个人笔记不覆盖)。\n",
        encoding="utf-8")

    await conn.close()
    print(f"完成: {n_theme} 主题 | {n_concept} 概念 | {n_ku} KU → {root}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
